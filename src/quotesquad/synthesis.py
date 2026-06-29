from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import cast

import httpx2
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from quotesquad.config import Settings
from quotesquad.http_client import create_async_client
from quotesquad.money import dollars
from quotesquad.schemas import (
    AgentFinding,
    ConfidenceStatus,
    MoneyModel,
    ProviderGap,
    Synthesis,
    VerifiedAnalysis,
)


class CerebrasMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    content: str


class CerebrasChoice(BaseModel):
    model_config = ConfigDict(frozen=True)

    message: CerebrasMessage


class CerebrasResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    choices: tuple[CerebrasChoice, ...]


class SynthesisPayload(BaseModel):
    model_config = ConfigDict(frozen=True)

    verdict: str
    summary: str
    negotiation_notes: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def accept_guidance_shape(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        payload = cast("Mapping[object, object]", value)
        guidance = _text_value(payload, "negotiation_guidance") or _text_value(payload, "guidance")
        if guidance is None and "negotiation_notes" not in payload and "notes" not in payload:
            return payload
        verdict = _text_value(payload, "verdict") or "Challenge selected line items with citations."
        summary = _text_value(payload, "summary") or guidance or verdict
        return {
            "verdict": verdict,
            "summary": summary,
            "negotiation_notes": _note_values(payload, summary),
        }


async def synthesize(verified: VerifiedAnalysis, settings: Settings) -> Synthesis:
    fallback = _deterministic_synthesis(verified)
    secret = settings.cerebras_api_key
    if secret is None:
        gap = ProviderGap(
            provider="cerebras",
            reason="QUOTESQUAD_CEREBRAS_API_KEY is not set.",
            blocks="LLM-authored personalized negotiation notes",
        )
        return fallback.model_copy(update={"provider_gaps": (*fallback.provider_gaps, gap)})
    try:
        llm_payload = await _call_cerebras(verified, settings, secret.get_secret_value())
    except (httpx2.HTTPError, ValidationError, ValueError):
        gap = ProviderGap(
            provider="cerebras",
            reason="Cerebras synthesis failed; deterministic synthesis was used.",
            blocks="LLM-authored personalized negotiation notes",
        )
        return fallback.model_copy(update={"provider_gaps": (*fallback.provider_gaps, gap)})
    return fallback.model_copy(
        update={
            "verdict": llm_payload.verdict,
            "summary": llm_payload.summary,
            "negotiation_notes": llm_payload.negotiation_notes,
        }
    )


def _deterministic_synthesis(verified: VerifiedAnalysis) -> Synthesis:
    actionable = tuple(
        finding
        for finding in verified.findings
        if finding.status in {ConfidenceStatus.VERIFIED, ConfidenceStatus.CAVEATED}
    )
    savings = _savings_range(actionable)
    if actionable:
        verdict = "Challenge selected line items with citations."
        summary = f"{len(actionable)} finding(s) meet the confidence gate for negotiation."
    else:
        verdict = "Request more source support before challenging price."
        summary = "No finding crossed the confidence gate for a sourced savings claim."
    return Synthesis(
        verdict=verdict,
        summary=summary,
        savings_low=savings[0],
        savings_high=savings[1],
        negotiation_notes=_notes(actionable),
    )


async def _call_cerebras(
    verified: VerifiedAnalysis,
    settings: Settings,
    api_key: str,
) -> SynthesisPayload:
    body = {
        "model": settings.cerebras_model,
        "reasoning_effort": "medium",
        "messages": (
            {
                "role": "system",
                "content": (
                    "You write concise negotiation guidance strictly grounded in the provided "
                    "structured findings. Do not add prices, statutes, sources, or facts."
                ),
            },
            {"role": "user", "content": verified.model_dump_json()},
        ),
        "response_format": {"type": "json_object"},
    }
    headers = {"authorization": f"Bearer {api_key}", "content-type": "application/json"}
    async with create_async_client(settings.cerebras_base_url, headers) as client:
        response = await client.post("/chat/completions", json=body)
        _ = response.raise_for_status()
    parsed = CerebrasResponse.model_validate_json(response.text)
    if not parsed.choices:
        raise ValueError("Cerebras returned no choices")
    return SynthesisPayload.model_validate_json(parsed.choices[0].message.content)


def _savings_range(findings: tuple[AgentFinding, ...]) -> tuple[MoneyModel, MoneyModel]:
    total = sum(
        (finding.delta.amount for finding in findings if finding.delta is not None), Decimal("0")
    )
    low = (total * Decimal("0.55")).quantize(Decimal("0.01"))
    high = total.quantize(Decimal("0.01"))
    return dollars(low), dollars(high)


def _notes(findings: tuple[AgentFinding, ...]) -> tuple[str, ...]:
    if not findings:
        return (
            "Ask for itemized labor guides, part numbers, and source links before negotiating.",
        )
    return tuple(
        f"Lead with: {finding.title}. Keep the cited benchmark attached." for finding in findings
    )


def _text_value(payload: Mapping[object, object], key: str) -> str | None:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _note_values(payload: Mapping[object, object], fallback: str) -> tuple[str, ...]:
    value = payload.get("negotiation_notes", payload.get("notes"))
    if isinstance(value, str) and value.strip():
        return (value.strip(),)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        notes = tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
        if notes:
            return notes
    return (fallback,)
