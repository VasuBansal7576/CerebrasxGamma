from __future__ import annotations

import httpx2
from pydantic import ValidationError

from quotesquad.confidence import confidence_status
from quotesquad.config import Settings
from quotesquad.schemas import (
    AgentFinding,
    AgentResult,
    Citation,
    ProviderGap,
    QuoteSchema,
    QuoteType,
    SourceType,
)
from quotesquad.vendor_directory import (
    OsmCandidate,
    VendorLookupError,
    VendorSearch,
    public_candidates,
)


async def alternative_vendor_agent(quote: QuoteSchema, settings: Settings) -> AgentResult:
    search = _search_for_quote(quote.quote_type)
    if search is None:
        return _gap("Quote type has no public alternative-vendor search yet.")
    if quote.zip_code is None:
        return _gap("A ZIP code is required for nearby alternative-vendor lookup.")
    try:
        candidates = await public_candidates(settings, search, quote.zip_code[:5])
    except (httpx2.HTTPError, ValidationError, VendorLookupError) as error:
        return _gap(str(error) or "OpenStreetMap vendor lookup failed.")
    result = alternative_vendor_result(quote, candidates, search.label)
    if result.findings:
        return result
    return _gap("OpenStreetMap returned no named nearby vendors for this quote type.")


def alternative_vendor_result(
    quote: QuoteSchema,
    candidates: tuple[OsmCandidate, ...],
    label: str,
) -> AgentResult:
    findings = tuple(_finding(quote, candidate, label) for candidate in candidates[:3])
    return AgentResult(agent="alternative", findings=findings)


def _search_for_quote(quote_type: QuoteType) -> VendorSearch | None:
    match quote_type:
        case QuoteType.AUTO:
            return VendorSearch("auto repair", (("shop", "car_repair"),))
        case QuoteType.CONTRACTOR:
            return VendorSearch(
                "contractor",
                (
                    ("craft", "plumber"),
                    ("craft", "electrician"),
                    ("craft", "carpenter"),
                    ("craft", "painter"),
                    ("craft", "roofer"),
                    ("shop", "hardware"),
                ),
            )
        case QuoteType.HVAC:
            return VendorSearch("HVAC or mechanical contractor", (("craft", "hvac"),))
        case QuoteType.DENTAL:
            return VendorSearch("dentist", (("amenity", "dentist"),))
        case QuoteType.LEGAL:
            return VendorSearch("law office", (("office", "lawyer"),))
        case QuoteType.UNKNOWN:
            return None


def _finding(quote: QuoteSchema, candidate: OsmCandidate, label: str) -> AgentFinding:
    contact = _contact(candidate)
    zip_code = quote.zip_code or "the submitted ZIP"
    return AgentFinding(
        agent="alternative",
        line_item_index=None,
        category="alternative_vendor",
        title=f"Public directory alternative: {candidate.name}",
        finding=(
            f"OpenStreetMap lists {candidate.name} as a nearby {label} option near {zip_code}"
            f"{contact}. Use it as a call target, not as proof of licensing, ratings, or open hours."
        ),
        quoted=None,
        benchmark=None,
        delta=None,
        confidence=0.62,
        status=confidence_status(0.62),
        citations=(
            Citation(
                title=f"OpenStreetMap listing for {candidate.name}",
                url=candidate.osm_url,
                source_type=SourceType.EXTERNAL,
            ),
        ),
    )


def _contact(candidate: OsmCandidate) -> str:
    if candidate.phone and candidate.website:
        return f" with phone {candidate.phone} and website {candidate.website}"
    if candidate.phone:
        return f" with phone {candidate.phone}"
    if candidate.website:
        return f" with website {candidate.website}"
    return ""


def _gap(reason: str) -> AgentResult:
    return AgentResult(
        agent="alternative",
        findings=(),
        gaps=(
            ProviderGap(
                provider="openstreetmap",
                reason=reason,
                blocks="Free public alternative-vendor candidates",
            ),
        ),
    )
