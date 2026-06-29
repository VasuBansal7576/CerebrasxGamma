from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from quotesquad.config import get_settings
from quotesquad.db import SessionDep
from quotesquad.document import text_from_upload
from quotesquad.pdf import render_pdf
from quotesquad.repository import calibration, get_analysis, save_feedback, vendor_intelligence
from quotesquad.schemas import FeedbackOutcome, FeedbackRequest, MoneyModel
from quotesquad.service import AnalysisInput, analyze_text

router = APIRouter()
templates = Jinja2Templates(directory="src/quotesquad/templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html", {"error": None})


@router.post("/analyze")
async def analyze_form(
    request: Request,
    session: SessionDep,
    quote_text: Annotated[str, Form()] = "",
    zip_code: Annotated[str, Form()] = "",
    consent_to_learn: Annotated[bool, Form()] = False,
    upload: Annotated[UploadFile | None, File()] = None,
) -> Response:
    settings = get_settings()
    document = await text_from_upload(upload, settings) if upload is not None else None
    combined = "\n".join(part for part in (quote_text, document.text if document else "") if part)
    if not combined and document is None:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"error": "Paste a quote or upload a text/PDF quote."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    gaps = document.gaps if document is not None else ()
    analysis = await analyze_text(
        AnalysisInput(
            text=combined,
            zip_code=zip_code or None,
            consent_to_learn=consent_to_learn,
            document_gaps=gaps,
        ),
        session,
        settings,
    )
    return RedirectResponse(f"/analyses/{analysis.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/analyses/{analysis_id}", response_class=HTMLResponse)
async def report(request: Request, analysis_id: str, session: SessionDep) -> HTMLResponse:
    analysis = await get_analysis(session, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return templates.TemplateResponse(request, "report.html", {"analysis": analysis})


@router.post("/analyses/{analysis_id}/feedback")
async def feedback_form(
    analysis_id: str,
    session: SessionDep,
    outcome: Annotated[FeedbackOutcome, Form()],
    negotiated_savings: Annotated[str, Form()] = "0",
    notes: Annotated[str, Form()] = "",
) -> RedirectResponse:
    try:
        savings = Decimal(negotiated_savings or "0")
    except InvalidOperation:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Negotiated savings must be a dollar amount.",
        ) from None
    if savings < Decimal("0"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Negotiated savings cannot be negative.",
        )
    feedback = await save_feedback(
        session,
        analysis_id,
        FeedbackRequest(
            outcome=outcome,
            negotiated_savings=MoneyModel(amount=savings),
            notes=notes or None,
        ),
    )
    if feedback is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return RedirectResponse(
        f"/analyses/{analysis_id}#feedback", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/enterprise", response_class=HTMLResponse)
async def enterprise(request: Request, session: SessionDep) -> HTMLResponse:
    vendors = await vendor_intelligence(session)
    calibration_rows = await calibration(session)
    return templates.TemplateResponse(
        request,
        "enterprise.html",
        {"vendors": vendors, "calibration_rows": calibration_rows},
    )


@router.get("/analyses/{analysis_id}/report.pdf")
async def pdf_report(analysis_id: str, session: SessionDep) -> Response:
    analysis = await get_analysis(session, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    return Response(
        content=render_pdf(analysis),
        media_type="application/pdf",
        headers={"content-disposition": f'attachment; filename="quotesquad-{analysis.id}.pdf"'},
    )
