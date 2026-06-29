from __future__ import annotations

from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from quotesquad.db import (
    AnalysisRecord,
    FeedbackRecord,
    PricingObservationRecord,
    WhiteLabelRecord,
)
from quotesquad.money import dollars
from quotesquad.schemas import (
    AnalysisRead,
    CalibrationRead,
    FeedbackOutcome,
    FeedbackRead,
    FeedbackRequest,
    QuoteType,
    RegionalBenchmarkRead,
    VendorIntelligenceRead,
    WhiteLabelConfig,
)


async def save_analysis(
    session: AsyncSession,
    analysis: AnalysisRead,
    consent_to_learn: bool,
) -> None:
    record = AnalysisRecord(
        id=analysis.id,
        status=analysis.status.value,
        quote_type=analysis.quote.quote_type.value,
        vendor=analysis.quote.vendor,
        consent_to_learn=consent_to_learn,
        result_json=analysis.model_dump_json(),
    )
    session.add(record)
    if consent_to_learn and analysis.quote.zip_code is not None:
        session.add_all(_pricing_observations(analysis))
    await session.commit()


async def get_analysis(session: AsyncSession, analysis_id: str) -> AnalysisRead | None:
    result = await session.execute(select(AnalysisRecord).where(AnalysisRecord.id == analysis_id))
    record = result.scalar_one_or_none()
    if record is None:
        return None
    return AnalysisRead.model_validate_json(record.result_json)


async def delete_analysis(session: AsyncSession, analysis_id: str) -> bool:
    analysis = await get_analysis(session, analysis_id)
    if analysis is None:
        return False
    _ = await session.execute(delete(AnalysisRecord).where(AnalysisRecord.id == analysis_id))
    _ = await session.execute(
        delete(FeedbackRecord).where(FeedbackRecord.analysis_id == analysis_id)
    )
    _ = await session.execute(
        delete(PricingObservationRecord).where(PricingObservationRecord.analysis_id == analysis_id)
    )
    await session.commit()
    return True


async def save_feedback(
    session: AsyncSession,
    analysis_id: str,
    payload: FeedbackRequest,
) -> FeedbackRead | None:
    analysis = await get_analysis(session, analysis_id)
    if analysis is None:
        return None
    categories = tuple(sorted({finding.category for finding in analysis.findings}))
    record = FeedbackRecord(
        analysis_id=analysis_id,
        outcome=payload.outcome.value,
        negotiated_savings=f"{payload.negotiated_savings.amount}",
        categories="\n".join(categories),
        notes=payload.notes,
    )
    session.add(record)
    await session.commit()
    return FeedbackRead(
        analysis_id=analysis_id,
        outcome=payload.outcome,
        negotiated_savings=payload.negotiated_savings,
        calibrated_categories=categories,
    )


async def regional_benchmarks(
    session: AsyncSession,
    zip_prefix: str,
) -> tuple[RegionalBenchmarkRead, ...]:
    result = await session.execute(
        select(PricingObservationRecord).where(
            PricingObservationRecord.zip_prefix == zip_prefix[:5]
        )
    )
    records = tuple(result.scalars().all())
    grouped: dict[tuple[str, str, str], list[Decimal]] = {}
    for record in records:
        key = (record.quote_type, record.zip_prefix, record.category)
        grouped.setdefault(key, []).append(Decimal(record.amount))
    rows: list[RegionalBenchmarkRead] = []
    for (quote_type, zip_code, category), amounts in grouped.items():
        average = sum(amounts, Decimal("0")) / Decimal(len(amounts))
        rows.append(
            RegionalBenchmarkRead(
                quote_type=QuoteType(quote_type),
                zip_prefix=zip_code,
                category=category,
                sample_size=len(amounts),
                average_amount=dollars(average),
            )
        )
    return tuple(rows)


async def calibration(session: AsyncSession) -> tuple[CalibrationRead, ...]:
    result = await session.execute(select(FeedbackRecord))
    records = tuple(result.scalars().all())
    totals: dict[str, int] = {}
    wins: dict[str, int] = {}
    for record in records:
        for category in record.categories.splitlines():
            totals[category] = totals.get(category, 0) + 1
            if record.outcome == FeedbackOutcome.WON_DISCOUNT.value:
                wins[category] = wins.get(category, 0) + 1
    return tuple(
        CalibrationRead(
            category=category,
            sample_size=sample_size,
            success_rate=wins.get(category, 0) / sample_size,
            confidence_multiplier=_confidence_multiplier(wins.get(category, 0), sample_size),
        )
        for category, sample_size in sorted(totals.items())
    )


async def save_white_label(
    session: AsyncSession,
    config: WhiteLabelConfig,
) -> WhiteLabelConfig:
    existing = await session.get(WhiteLabelRecord, config.organization_id)
    if existing is None:
        session.add(
            WhiteLabelRecord(
                organization_id=config.organization_id,
                config_json=config.model_dump_json(),
            )
        )
    else:
        existing.config_json = config.model_dump_json()
    await session.commit()
    return config


async def get_white_label(
    session: AsyncSession,
    organization_id: str,
) -> WhiteLabelConfig | None:
    record = await session.get(WhiteLabelRecord, organization_id)
    if record is None:
        return None
    return WhiteLabelConfig.model_validate_json(record.config_json)


async def vendor_intelligence(
    session: AsyncSession,
    vendor: str | None = None,
) -> tuple[VendorIntelligenceRead, ...]:
    result = await session.execute(select(AnalysisRecord))
    analyses = tuple(
        AnalysisRead.model_validate_json(record.result_json) for record in result.scalars()
    )
    grouped: dict[str, list[AnalysisRead]] = {}
    for analysis in analyses:
        vendor_name = analysis.quote.vendor or "unknown"
        if vendor is not None and vendor_name.lower() != vendor.lower():
            continue
        grouped.setdefault(vendor_name, []).append(analysis)
    return tuple(_vendor_row(name, rows) for name, rows in sorted(grouped.items()))


def _pricing_observations(analysis: AnalysisRead) -> tuple[PricingObservationRecord, ...]:
    zip_code = analysis.quote.zip_code
    if zip_code is None:
        return ()
    return tuple(
        PricingObservationRecord(
            analysis_id=analysis.id,
            quote_type=analysis.quote.quote_type.value,
            zip_prefix=zip_code[:5],
            category=item.kind.value,
            amount=f"{item.total.amount}",
        )
        for item in analysis.quote.line_items
    )


def _confidence_multiplier(wins: int, total: int) -> float:
    rate = wins / total
    if total < 5:
        return 1.0
    return max(0.75, min(1.15, 0.85 + rate * 0.30))


def _vendor_row(vendor: str, analyses: list[AnalysisRead]) -> VendorIntelligenceRead:
    findings = tuple(finding for analysis in analyses for finding in analysis.findings)
    total_delta = sum(
        (finding.delta.amount for finding in findings if finding.delta is not None), Decimal("0")
    )
    return VendorIntelligenceRead(
        vendor=vendor,
        analyses=len(analyses),
        flagged_findings=len(findings),
        total_potential_delta=dollars(total_delta),
        repeat_flag=len(analyses) >= 3 and len(findings) >= 5,
    )
