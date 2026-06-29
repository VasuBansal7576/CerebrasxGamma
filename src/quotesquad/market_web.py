from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html import unescape
from typing import Final
from urllib.parse import urlencode

import httpx2

from quotesquad.confidence import confidence_status, positive_delta, weighted_confidence
from quotesquad.http_client import create_async_client
from quotesquad.money import dollars
from quotesquad.schemas import (
    AgentFinding,
    AgentResult,
    Citation,
    LineItemKind,
    ProviderGap,
    QuoteSchema,
    SourceType,
)

EBAY_ORIGIN: Final = "https://www.ebay.com"
READER_ORIGIN: Final = "https://r.jina.ai"


@dataclass(frozen=True, slots=True)
class WebPriceBenchmark:
    label: str
    p75: Decimal
    sample_size: int
    source: Citation


async def ebay_public_agent(quote: QuoteSchema) -> AgentResult:
    items = tuple(item for item in quote.line_items if item.kind is LineItemKind.PART)
    if not items:
        return AgentResult(agent="ebay_public", findings=())
    findings: list[AgentFinding] = []
    gaps: list[ProviderGap] = []
    for item in items:
        try:
            benchmark = await _fetch_benchmark(item.description)
        except httpx2.HTTPError:
            gaps.append(_gap("eBay public search blocked or failed."))
            continue
        if benchmark is None:
            gaps.append(_gap(f"No public eBay prices parsed for {item.description}."))
            continue
        delta = positive_delta(item.total, dollars(benchmark.p75))
        if delta is None:
            continue
        confidence = weighted_confidence(0.61, 0.72, benchmark.sample_size)
        findings.append(
            AgentFinding(
                agent="ebay_public",
                line_item_index=item.index,
                category="parts_price",
                title="Public eBay listings price this part lower",
                finding=(
                    f"Public eBay listings for {benchmark.label} have p75 around "
                    f"{benchmark.p75}. Treat this as public-web evidence, not a licensed catalog."
                ),
                quoted=item.total,
                benchmark=dollars(benchmark.p75),
                delta=delta,
                confidence=confidence,
                status=confidence_status(confidence),
                citations=(benchmark.source,),
            )
        )
    return AgentResult(agent="ebay_public", findings=tuple(findings), gaps=tuple(gaps))


def parse_ebay_prices(text: str) -> tuple[Decimal, ...]:
    amounts: list[Decimal] = []
    tokens = unescape(text).replace("USD", "$").split("$")
    for token in tokens[1:]:
        amount = _amount_prefix(token)
        if amount is not None and Decimal("5") <= amount <= Decimal("5000"):
            amounts.append(amount)
    return tuple(amounts[:40])


async def _fetch_benchmark(description: str) -> WebPriceBenchmark | None:
    search_url = _search_url(description)
    html = await _fetch_direct(description)
    prices = parse_ebay_prices(html)
    if len(prices) < 3:
        html = await _fetch_reader(search_url)
        prices = parse_ebay_prices(html)
    if len(prices) < 3:
        return None
    ordered = tuple(sorted(prices))
    p75 = ordered[int((len(ordered) - 1) * 0.75)]
    return WebPriceBenchmark(
        label=description,
        p75=p75,
        sample_size=len(ordered),
        source=Citation(
            title="eBay public search listings",
            url=search_url,
            source_type=SourceType.EXTERNAL,
        ),
    )


async def _fetch_direct(description: str) -> str:
    async with create_async_client(EBAY_ORIGIN, _headers()) as client:
        response = await client.get("/sch/i.html", params=_params(description))
        _ = response.raise_for_status()
    return response.text


async def _fetch_reader(search_url: str) -> str:
    async with create_async_client(READER_ORIGIN, _headers()) as client:
        response = await client.get(f"/{search_url}")
        _ = response.raise_for_status()
    return response.text


def _params(description: str) -> tuple[tuple[str, str], ...]:
    return (
        ("_nkw", description),
        ("_sacat", "0"),
        ("LH_BIN", "1"),
        ("_ipg", "30"),
    )


def _search_url(description: str) -> str:
    return f"{EBAY_ORIGIN}/sch/i.html?{urlencode(_params(description))}"


def _headers() -> dict[str, str]:
    return {
        "accept": "text/html,application/xhtml+xml",
        "user-agent": "Mozilla/5.0 QuoteSquad/0.1",
    }


def _amount_prefix(token: str) -> Decimal | None:
    raw: list[str] = []
    for character in token.strip():
        if character.isdigit() or character in {",", "."}:
            raw.append(character)
            continue
        break
    if not raw:
        return None
    try:
        return Decimal("".join(raw).replace(",", ""))
    except InvalidOperation:
        return None


def _gap(reason: str) -> ProviderGap:
    return ProviderGap(
        provider="ebay_public_web",
        reason=reason,
        blocks="Public parts price comparison",
    )
