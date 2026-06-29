from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import override

from fastapi import UploadFile
from pypdf import PdfReader

from quotesquad.config import Settings
from quotesquad.money import add_money, dollars
from quotesquad.ocr import extract_image_text
from quotesquad.pii import scrub_pii
from quotesquad.schemas import (
    LineItem,
    LineItemKind,
    MoneyModel,
    ProviderGap,
    QuoteSchema,
    QuoteType,
)
from quotesquad.vehicle import parse_vehicle

PRICE_RE = re.compile(r"\$?\s*((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{2})?)")
HOURS_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|hr)\b", re.I)
ZIP_RE = re.compile(r"\b\d{5}(?:-\d{4})?\b")
DATE_RE = re.compile(r"\b(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b")


@dataclass(frozen=True, slots=True)
class DocumentText:
    text: str
    gaps: tuple[ProviderGap, ...] = ()


class DocumentError(Exception):
    @override
    def __str__(self) -> str:
        return "document could not be processed"


@dataclass(frozen=True, slots=True)
class UploadTooLargeError(DocumentError):
    size: int
    limit: int

    @override
    def __str__(self) -> str:
        return f"upload is {self.size} bytes; limit is {self.limit} bytes"


async def text_from_upload(upload: UploadFile, settings: Settings) -> DocumentText:
    payload = await upload.read()
    if len(payload) > settings.max_upload_bytes:
        raise UploadTooLargeError(size=len(payload), limit=settings.max_upload_bytes)
    suffix = Path(upload.filename or "").suffix.lower()
    match suffix:
        case ".pdf":
            return DocumentText(text=_text_from_pdf(payload))
        case ".txt" | ".csv" | ".md" | "":
            return DocumentText(text=payload.decode("utf-8", errors="replace"))
        case ".jpg" | ".jpeg" | ".png" | ".heic" | ".webp":
            text, gaps = extract_image_text(payload, suffix)
            return DocumentText(text=text, gaps=gaps)
        case _ as unreachable:
            gap = ProviderGap(
                provider="ingestion",
                reason=f"Unsupported file extension: {unreachable or 'none'}",
                blocks="Document extraction",
            )
            return DocumentText(text="", gaps=(gap,))


def extract_quote(
    text: str, fallback_zip: str | None, gaps: tuple[ProviderGap, ...] = ()
) -> QuoteSchema:
    scrubbed, redactions = scrub_pii(text)
    line_items = tuple(_parse_line_items(scrubbed))
    vehicle = parse_vehicle(scrubbed)
    zip_code = fallback_zip or _first_match(ZIP_RE, scrubbed)
    quote_date = _parse_date(scrubbed)
    total = _quote_total(scrubbed, line_items)
    extraction_gaps = gaps
    if not line_items:
        extraction_gaps = (
            *extraction_gaps,
            ProviderGap(
                provider="entity_extractor",
                reason="No line items with dollar amounts were found.",
                blocks="Price comparison",
            ),
        )
    return QuoteSchema(
        quote_type=_classify(scrubbed),
        vendor=_vendor(scrubbed),
        quote_date=quote_date,
        quote_total=total,
        zip_code=zip_code,
        vehicle_year=vehicle.year if vehicle is not None else None,
        vehicle_make=vehicle.make if vehicle is not None else None,
        vehicle_model=vehicle.model if vehicle is not None else None,
        line_items=line_items,
        redactions=redactions,
        extraction_gaps=extraction_gaps,
    )


def _text_from_pdf(payload: bytes) -> str:
    reader = PdfReader(BytesIO(payload))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _parse_line_items(text: str) -> list[LineItem]:
    items: list[LineItem] = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.strip().split())
        if not line or _is_total_line(line) or _is_context_line(line):
            continue
        amount_span = _last_amount_span(line)
        if amount_span is None:
            continue
        amount, start, end = amount_span
        without_price = f"{line[:start]}{line[end:]}"
        description = " ".join(HOURS_RE.sub("", without_price).strip(" -:\t").split())
        if not description:
            continue
        hours = _hours(line)
        items.append(
            LineItem(
                index=len(items),
                description=description,
                kind=_kind(description),
                total=dollars(amount),
                quoted_hours=hours,
                source_line=line,
            )
        )
    return items


def _classify(text: str) -> QuoteType:
    lowered = text.lower()
    match True:
        case _ if any(
            term in lowered
            for term in ("drywall", "roof", "plumbing", "contractor", "toilet", "water heater")
        ):
            return QuoteType.CONTRACTOR
        case _ if any(
            term in lowered for term in ("brake", "rotor", "oil", "battery", "vehicle", "tire")
        ):
            return QuoteType.AUTO
        case _ if any(term in lowered for term in ("furnace", "hvac", "condenser", "compressor")):
            return QuoteType.HVAC
        case _ if any(term in lowered for term in ("tooth", "dental", "crown", "x-ray")):
            return QuoteType.DENTAL
        case _ if any(term in lowered for term in ("retainer", "attorney", "legal", "filing")):
            return QuoteType.LEGAL
        case _:
            return QuoteType.UNKNOWN


def _kind(description: str) -> LineItemKind:
    lowered = description.lower()
    match True:
        case _ if "labor" in lowered or HOURS_RE.search(description) is not None:
            return LineItemKind.LABOR
        case _ if any(
            term in lowered for term in ("rotor", "pad", "battery", "filter", "part", "compressor")
        ):
            return LineItemKind.PART
        case _ if any(term in lowered for term in ("fee", "shop supplies", "disposal", "admin")):
            return LineItemKind.FEE
        case _ if any(term in lowered for term in ("service", "flush", "clean", "diagnostic")):
            return LineItemKind.SERVICE
        case _:
            return LineItemKind.UNKNOWN


def _last_amount(line: str) -> Decimal | None:
    amount_span = _last_amount_span(line)
    return amount_span[0] if amount_span is not None else None


def _last_amount_span(line: str) -> tuple[Decimal, int, int] | None:
    last_match: re.Match[str] | None = None
    for match in PRICE_RE.finditer(line):
        if not _looks_like_price(match):
            continue
        last_match = match
    if last_match is None:
        return None
    amount_text: str | None = None
    amount_text = last_match.group(1)
    if amount_text is None:
        return None
    try:
        amount = Decimal(amount_text.replace(",", ""))
    except InvalidOperation:
        return None
    return amount, last_match.start(), last_match.end()


def _looks_like_price(match: re.Match[str]) -> bool:
    token = match.group(0)
    amount_text = match.group(1)
    return "$" in token or "." in amount_text or "," in amount_text


def _hours(line: str) -> Decimal | None:
    match = HOURS_RE.search(line)
    if match is None:
        return None
    try:
        return Decimal(match.group(1))
    except InvalidOperation:
        return None


def _quote_total(text: str, line_items: tuple[LineItem, ...]) -> MoneyModel | None:
    for line in text.splitlines():
        if _is_total_line(line):
            amount = _last_amount(line)
            if amount is not None:
                return dollars(amount)
    return add_money(tuple(item.total for item in line_items)) if line_items else None


def _parse_date(text: str) -> date | None:
    match = DATE_RE.search(text)
    if match is None:
        return None
    year, month, day = (int(match.group(index)) for index in range(1, 4))
    return date(year, month, day)


def _vendor(text: str) -> str | None:
    for line in text.splitlines():
        normalized = line.strip()
        if normalized and not PRICE_RE.search(normalized):
            return normalized[:120]
    return None


def _first_match(regex: re.Pattern[str], text: str) -> str | None:
    match = regex.search(text)
    return match.group(0) if match is not None else None


def _is_total_line(line: str) -> bool:
    lowered = line.lower()
    return any(label in lowered for label in ("total", "subtotal", "tax", "balance due"))


def _is_context_line(line: str) -> bool:
    lowered = line.lower()
    return lowered.startswith(("zip ", "zip:", "postal code")) or DATE_RE.search(line) is not None
