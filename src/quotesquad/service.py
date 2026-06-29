from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from quotesquad.actions import build_actions
from quotesquad.agents import run_agents
from quotesquad.confidence import confidence_status
from quotesquad.config import Settings
from quotesquad.document import DocumentText, extract_quote
from quotesquad.public_data import run_public_agents
from quotesquad.repository import calibration, save_analysis
from quotesquad.schemas import (
    AgentFinding,
    AnalysisRead,
    AnalysisStatus,
    AnalyzeQuoteRequest,
    CalibrationRead,
    ProviderGap,
    VerifiedAnalysis,
)
from quotesquad.synthesis import synthesize
from quotesquad.verification import verify


@dataclass(frozen=True, slots=True)
class AnalysisInput:
    text: str
    zip_code: str | None
    consent_to_learn: bool
    document_gaps: tuple[ProviderGap, ...] = ()


async def analyze_request(
    payload: AnalyzeQuoteRequest,
    session: AsyncSession,
    settings: Settings,
) -> AnalysisRead:
    document = DocumentText(text=payload.quote_text)
    return await analyze_text(
        AnalysisInput(
            text=document.text,
            zip_code=payload.zip_code,
            consent_to_learn=payload.consent_to_learn,
            document_gaps=document.gaps,
        ),
        session,
        settings,
    )


async def analyze_text(
    payload: AnalysisInput,
    session: AsyncSession,
    settings: Settings,
) -> AnalysisRead:
    quote = extract_quote(payload.text, payload.zip_code, payload.document_gaps)
    agent_results = (*run_agents(quote), *await run_public_agents(quote, settings))
    verified = verify(quote, agent_results)
    verified = _apply_calibration(verified, await calibration(session))
    synthesis = await synthesize(verified, settings)
    gaps = (*verified.gaps, *synthesis.provider_gaps)
    findings = verified.findings
    actions = build_actions(quote, findings)
    status = AnalysisStatus.PARTIAL if gaps else AnalysisStatus.COMPLETE
    analysis = AnalysisRead(
        id=uuid4().hex,
        status=status,
        created_at=datetime.now(UTC),
        quote=quote,
        findings=findings,
        conflicts=verified.conflicts,
        gaps=gaps,
        synthesis=synthesis,
        actions=actions,
    )
    await save_analysis(session, analysis, payload.consent_to_learn)
    return analysis


def _apply_calibration(
    verified: VerifiedAnalysis,
    calibration_rows: tuple[CalibrationRead, ...],
) -> VerifiedAnalysis:
    multipliers = {row.category: row.confidence_multiplier for row in calibration_rows}
    if not multipliers:
        return verified
    findings = tuple(_calibrated_finding(finding, multipliers) for finding in verified.findings)
    return verified.model_copy(update={"findings": findings})


def _calibrated_finding(
    finding: AgentFinding,
    multipliers: dict[str, float],
) -> AgentFinding:
    multiplier = multipliers.get(finding.category, 1.0)
    confidence = min(1.0, round(finding.confidence * multiplier, 2))
    return finding.model_copy(
        update={"confidence": confidence, "status": confidence_status(confidence)}
    )
