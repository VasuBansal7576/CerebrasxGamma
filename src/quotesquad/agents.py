from __future__ import annotations

from quotesquad.confidence import confidence_status, positive_delta, weighted_confidence
from quotesquad.knowledge import (
    SEED_CITATION,
    contractor_benchmark,
    labor_benchmark,
    part_benchmark,
    regional_labor_rate,
)
from quotesquad.money import dollars
from quotesquad.schemas import (
    AgentFinding,
    AgentResult,
    LineItem,
    LineItemKind,
    MoneyModel,
    ProviderGap,
    QuoteSchema,
    QuoteType,
)


def run_agents(quote: QuoteSchema) -> tuple[AgentResult, ...]:
    return (
        _labor_agent(quote),
        _parts_agent(quote),
        _contractor_agent(quote),
        _necessity_agent(quote),
        _alternative_agent(quote),
    )


def _labor_agent(quote: QuoteSchema) -> AgentResult:
    findings: list[AgentFinding] = []
    gaps: list[ProviderGap] = []
    regional = regional_labor_rate(quote.zip_code)
    if regional is None:
        gaps.append(
            ProviderGap(
                provider="regional_labor",
                reason="A ZIP code is required for regional labor comparison.",
                blocks="Labor rate confidence",
            )
        )
    for item in quote.line_items:
        if item.kind is not LineItemKind.LABOR:
            continue
        benchmark = labor_benchmark(item.description)
        if benchmark is None or regional is None or item.quoted_hours is None:
            findings.append(_unverified_labor_gap(item))
            continue
        expected = dollars(benchmark.standard_hours * regional.p75.amount)
        delta = positive_delta(item.total, expected)
        if delta is None:
            continue
        confidence = weighted_confidence(benchmark.source_quality, 0.84, regional.sample_size)
        findings.append(
            AgentFinding(
                agent="labor",
                line_item_index=item.index,
                category="labor_time",
                title="Labor time appears above benchmark",
                finding=(
                    f"Quoted {item.quoted_hours} hours for {item.description}; "
                    f"seed benchmark is {benchmark.standard_hours} hours at p75 regional labor."
                ),
                quoted=item.total,
                benchmark=expected,
                delta=delta,
                confidence=confidence,
                status=confidence_status(confidence),
                citations=(benchmark.source, regional.source),
            )
        )
    return AgentResult(agent="labor", findings=tuple(findings), gaps=tuple(gaps))


def _parts_agent(quote: QuoteSchema) -> AgentResult:
    findings: list[AgentFinding] = []
    for item in quote.line_items:
        if item.kind is not LineItemKind.PART:
            continue
        benchmark = part_benchmark(item.description)
        if benchmark is None:
            findings.append(_unverified_part_gap(item))
            continue
        delta = positive_delta(item.total, benchmark.p75)
        if delta is None:
            continue
        confidence = weighted_confidence(benchmark.source_quality, 0.80, benchmark.sample_size)
        findings.append(
            AgentFinding(
                agent="parts",
                line_item_index=item.index,
                category="parts_price",
                title="Part price appears above retail benchmark",
                finding=(
                    f"Quoted {item.total.amount} for {item.description}; "
                    f"seed p75 benchmark for {benchmark.label} is {benchmark.p75.amount}."
                ),
                quoted=item.total,
                benchmark=benchmark.p75,
                delta=delta,
                confidence=confidence,
                status=confidence_status(confidence),
                citations=(benchmark.source,),
            )
        )
    return AgentResult(agent="parts", findings=tuple(findings))


def _contractor_agent(quote: QuoteSchema) -> AgentResult:
    if quote.quote_type is not QuoteType.CONTRACTOR:
        return AgentResult(agent="contractor", findings=())
    findings: list[AgentFinding] = []
    gaps = (
        ProviderGap(
            provider="rsmeans",
            reason="RSMeans credential is not configured.",
            blocks="Licensed construction labor/material validation",
        ),
        ProviderGap(
            provider="home_depot",
            reason="Home Depot product API credential is not configured.",
            blocks="Live material price validation",
        ),
    )
    for item in quote.line_items:
        benchmark = contractor_benchmark(item.description)
        if benchmark is None:
            continue
        delta = positive_delta(item.total, benchmark.p75)
        if delta is None:
            continue
        confidence = weighted_confidence(benchmark.source_quality, 0.72, benchmark.sample_size)
        findings.append(
            AgentFinding(
                agent="contractor",
                line_item_index=item.index,
                category="contractor_price",
                title="Contractor line item appears above seed benchmark",
                finding=(
                    f"Quoted {item.total.amount} for {item.description}; "
                    f"seed p75 benchmark for {benchmark.label} is {benchmark.p75.amount}."
                ),
                quoted=item.total,
                benchmark=benchmark.p75,
                delta=delta,
                confidence=confidence,
                status=confidence_status(confidence),
                citations=(benchmark.source,),
            )
        )
    return AgentResult(agent="contractor", findings=tuple(findings), gaps=gaps)


def _necessity_agent(quote: QuoteSchema) -> AgentResult:
    findings: list[AgentFinding] = []
    for item in quote.line_items:
        lowered = item.description.lower()
        if "flush" not in lowered and "shop supplies" not in lowered:
            continue
        confidence = 0.62 if "flush" in lowered else 0.72
        benchmark: MoneyModel | None = dollars("0") if "shop supplies" in lowered else None
        delta = item.total if benchmark is not None else None
        findings.append(
            AgentFinding(
                agent="necessity",
                line_item_index=item.index,
                category="necessity",
                title="Item needs vendor justification",
                finding=(
                    "This item is commonly negotiable or requires a source-backed necessity explanation."
                ),
                quoted=item.total,
                benchmark=benchmark,
                delta=delta,
                confidence=confidence,
                status=confidence_status(confidence),
                citations=(SEED_CITATION,),
            )
        )
    return AgentResult(agent="necessity", findings=tuple(findings))


def _alternative_agent(_: QuoteSchema) -> AgentResult:
    gap = ProviderGap(
        provider="alternative_vendor",
        reason="Live licensing/open-hours lookup is not configured yet.",
        blocks="Alternative shop recommendations",
    )
    return AgentResult(agent="alternative", findings=(), gaps=(gap,))


def _unverified_labor_gap(item: LineItem) -> AgentFinding:
    return AgentFinding(
        agent="labor",
        line_item_index=item.index,
        category="labor_time",
        title="Labor benchmark unavailable",
        finding="The line item lacks hours, ZIP context, or a matching labor benchmark.",
        quoted=item.total,
        benchmark=None,
        delta=None,
        confidence=0.48,
        status=confidence_status(0.48),
        citations=(),
    )


def _unverified_part_gap(item: LineItem) -> AgentFinding:
    return AgentFinding(
        agent="parts",
        line_item_index=item.index,
        category="parts_price",
        title="Part benchmark unavailable",
        finding="No configured parts provider matched this description.",
        quoted=item.total,
        benchmark=None,
        delta=None,
        confidence=0.46,
        status=confidence_status(0.46),
        citations=(),
    )
