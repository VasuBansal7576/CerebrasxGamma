from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from quotesquad.auth import require_admin_api_key, require_api_key
from quotesquad.config import Settings, get_settings
from quotesquad.db import SessionDep
from quotesquad.readiness import (
    InfraReadiness,
    ProviderReadiness,
    infra_readiness,
    provider_readiness,
)
from quotesquad.repository import (
    calibration,
    delete_analysis,
    get_analysis,
    get_white_label,
    regional_benchmarks,
    save_feedback,
    save_white_label,
    vendor_intelligence,
)
from quotesquad.schemas import (
    AnalysisRead,
    AnalyzeQuoteRequest,
    CalibrationRead,
    ComplianceControl,
    EnterpriseAuditRead,
    EnterpriseAuditRequest,
    FeedbackRead,
    FeedbackRequest,
    RegionalBenchmarkRead,
    VendorIntelligenceRead,
    WhiteLabelConfig,
)
from quotesquad.service import analyze_request

router = APIRouter(
    prefix="/api",
    tags=["api"],
    dependencies=[Depends(require_api_key)],
)

SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/health")
async def health(settings: SettingsDep) -> dict[str, str]:
    llm = "configured" if settings.cerebras_api_key is not None else "missing"
    return {"status": "ok", "cerebras": llm}


@router.get(
    "/providers/status",
    response_model=ProviderReadiness,
    dependencies=[Depends(require_admin_api_key)],
)
async def providers_status(settings: SettingsDep) -> ProviderReadiness:
    return provider_readiness(settings)


@router.get(
    "/infra/readiness",
    response_model=InfraReadiness,
    dependencies=[Depends(require_admin_api_key)],
)
async def read_infra_readiness(settings: SettingsDep) -> InfraReadiness:
    return infra_readiness(settings)


@router.post("/analyses", response_model=AnalysisRead)
async def create_analysis(
    payload: AnalyzeQuoteRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> AnalysisRead:
    return await analyze_request(payload, session, settings)


@router.get("/analyses/{analysis_id}", response_model=AnalysisRead)
async def read_analysis(analysis_id: str, session: SessionDep) -> AnalysisRead:
    analysis = await get_analysis(session, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return analysis


@router.delete("/analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_analysis(analysis_id: str, session: SessionDep) -> Response:
    deleted = await delete_analysis(session, analysis_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/analyses/{analysis_id}/feedback", response_model=FeedbackRead)
async def create_feedback(
    analysis_id: str,
    payload: FeedbackRequest,
    session: SessionDep,
) -> FeedbackRead:
    feedback = await save_feedback(session, analysis_id, payload)
    if feedback is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return feedback


@router.get("/regional/{zip_prefix}", response_model=tuple[RegionalBenchmarkRead, ...])
async def read_regional_benchmarks(
    zip_prefix: str,
    session: SessionDep,
) -> tuple[RegionalBenchmarkRead, ...]:
    return await regional_benchmarks(session, zip_prefix)


@router.get("/calibration", response_model=tuple[CalibrationRead, ...])
async def read_calibration(session: SessionDep) -> tuple[CalibrationRead, ...]:
    return await calibration(session)


@router.post("/enterprise/audits", response_model=EnterpriseAuditRead)
async def create_enterprise_audit(
    payload: EnterpriseAuditRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> EnterpriseAuditRead:
    analysis = await analyze_request(
        AnalyzeQuoteRequest(
            quote_text=payload.quote_text,
            zip_code=payload.zip_code,
            consent_to_learn=True,
        ),
        session,
        settings,
    )
    return EnterpriseAuditRead(
        organization_id=payload.organization_id,
        external_ref=payload.external_ref,
        use_case=payload.use_case,
        analysis=analysis,
    )


@router.get("/enterprise/fleet/summary", response_model=tuple[VendorIntelligenceRead, ...])
async def fleet_summary(session: SessionDep) -> tuple[VendorIntelligenceRead, ...]:
    return await vendor_intelligence(session)


@router.put("/white-label/{organization_id}", response_model=WhiteLabelConfig)
async def upsert_white_label(
    organization_id: str,
    payload: WhiteLabelConfig,
    session: SessionDep,
) -> WhiteLabelConfig:
    config = payload.model_copy(update={"organization_id": organization_id})
    return await save_white_label(session, config)


@router.get("/white-label/{organization_id}", response_model=WhiteLabelConfig)
async def read_white_label(organization_id: str, session: SessionDep) -> WhiteLabelConfig:
    config = await get_white_label(session, organization_id)
    if config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Config not found")
    return config


@router.get("/vendors/intelligence", response_model=tuple[VendorIntelligenceRead, ...])
async def read_vendor_intelligence(session: SessionDep) -> tuple[VendorIntelligenceRead, ...]:
    return await vendor_intelligence(session)


@router.get("/vendors/{vendor}/intelligence", response_model=tuple[VendorIntelligenceRead, ...])
async def read_one_vendor_intelligence(
    vendor: str,
    session: SessionDep,
) -> tuple[VendorIntelligenceRead, ...]:
    return await vendor_intelligence(session, vendor)


@router.get("/compliance/controls", response_model=tuple[ComplianceControl, ...])
async def compliance_controls() -> tuple[ComplianceControl, ...]:
    return (
        ComplianceControl(
            key="raw_document_retention",
            status="implemented",
            evidence="Uploads are processed in memory; persisted records store scrubbed structured output only.",
        ),
        ComplianceControl(
            key="right_to_deletion",
            status="implemented",
            evidence="DELETE /api/analyses/{analysis_id} removes analysis, feedback, and observations.",
        ),
        ComplianceControl(
            key="hipaa_adjacent_track",
            status="gated",
            evidence="Medical/dental analyses do not send raw documents to external LLMs; BAA still required.",
        ),
        ComplianceControl(
            key="soc2_readiness",
            status="started",
            evidence="API auth, audit persistence, retention controls, and explicit provider gaps are present.",
        ),
    )
