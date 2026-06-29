from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import httpx2
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from quotesquad.confidence import confidence_status
from quotesquad.config import Settings
from quotesquad.http_client import create_async_client
from quotesquad.market_web import ebay_public_agent
from quotesquad.schemas import (
    AgentFinding,
    AgentResult,
    Citation,
    ProviderGap,
    QuoteSchema,
    SourceType,
)

STOPWORDS: Final = frozenset(
    ("and", "for", "the", "with", "system", "other", "unknown", "assembly", "vehicle")
)


class NhtsaRecall(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    campaign: str = Field(alias="NHTSACampaignNumber")
    component: str = Field(alias="Component")
    summary: str = Field(alias="Summary")


class NhtsaComplaint(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    odi_number: int = Field(alias="odiNumber")
    components: str
    summary: str


class NhtsaRecallResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    results: tuple[NhtsaRecall, ...] = ()


class NhtsaComplaintResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    results: tuple[NhtsaComplaint, ...] = ()


@dataclass(frozen=True, slots=True)
class NhtsaData:
    recalls: tuple[NhtsaRecall, ...]
    complaints: tuple[NhtsaComplaint, ...]


async def run_public_agents(quote: QuoteSchema, settings: Settings) -> tuple[AgentResult, ...]:
    ebay_result = await ebay_public_agent(quote)
    if quote.vehicle_year is None or quote.vehicle_make is None or quote.vehicle_model is None:
        return (ebay_result,)
    try:
        data = await _fetch_nhtsa(quote, settings)
    except (httpx2.HTTPError, ValidationError):
        return (
            ebay_result,
            AgentResult(
                agent="nhtsa",
                findings=(),
                gaps=(
                    ProviderGap(
                        provider="nhtsa",
                        reason="NHTSA public data lookup failed.",
                        blocks="Recall and complaint context",
                    ),
                ),
            ),
        )
    return (ebay_result, nhtsa_agent_result(quote, data))


def nhtsa_agent_result(quote: QuoteSchema, data: NhtsaData) -> AgentResult:
    findings = [
        *_recall_findings(quote, data.recalls),
        *_complaint_findings(quote, data.complaints),
    ]
    return AgentResult(agent="nhtsa", findings=tuple(findings))


async def _fetch_nhtsa(quote: QuoteSchema, settings: Settings) -> NhtsaData:
    params = _vehicle_params(quote)
    async with create_async_client(
        settings.nhtsa_base_url, {"accept": "application/json"}
    ) as client:
        recalls_response = await client.get("/recalls/recallsByVehicle", params=params)
        _ = recalls_response.raise_for_status()
        complaints_response = await client.get("/complaints/complaintsByVehicle", params=params)
        _ = complaints_response.raise_for_status()
    recalls = NhtsaRecallResponse.model_validate_json(recalls_response.text).results
    complaints = NhtsaComplaintResponse.model_validate_json(complaints_response.text).results
    return NhtsaData(recalls=recalls, complaints=complaints)


def _vehicle_params(quote: QuoteSchema) -> tuple[tuple[str, str], ...]:
    return (
        ("make", quote.vehicle_make or ""),
        ("model", quote.vehicle_model or ""),
        ("modelYear", str(quote.vehicle_year or "")),
    )


def _recall_findings(
    quote: QuoteSchema, recalls: tuple[NhtsaRecall, ...]
) -> tuple[AgentFinding, ...]:
    findings: list[AgentFinding] = []
    for item in quote.line_items:
        item_words = _words(item.description)
        for recall in recalls:
            if not item_words.intersection(_words(recall.component)):
                continue
            findings.append(
                AgentFinding(
                    agent="nhtsa",
                    line_item_index=item.index,
                    category="recall",
                    title="NHTSA recall may cover this item",
                    finding=(
                        f"{_vehicle_label(quote)} has NHTSA recall {recall.campaign} for "
                        f"{recall.component}. Ask whether this charge is covered before paying."
                    ),
                    quoted=item.total,
                    benchmark=None,
                    delta=None,
                    confidence=0.86,
                    status=confidence_status(0.86),
                    citations=(_recall_citation(quote, recall),),
                )
            )
            break
    return tuple(findings)


def _complaint_findings(
    quote: QuoteSchema, complaints: tuple[NhtsaComplaint, ...]
) -> tuple[AgentFinding, ...]:
    findings: list[AgentFinding] = []
    for item in quote.line_items:
        item_words = _words(item.description)
        matches = tuple(
            complaint
            for complaint in complaints
            if item_words.intersection(_words(complaint.components))
        )
        if len(matches) < 3:
            continue
        findings.append(
            AgentFinding(
                agent="nhtsa",
                line_item_index=item.index,
                category="complaint_trend",
                title="NHTSA complaints mention this component",
                finding=(
                    f"NHTSA has {len(matches)} complaint(s) for {_vehicle_label(quote)} involving "
                    f"{matches[0].components}. Ask the vendor to document diagnosis and necessity."
                ),
                quoted=item.total,
                benchmark=None,
                delta=None,
                confidence=0.71,
                status=confidence_status(0.71),
                citations=(_complaint_citation(quote),),
            )
        )
    return tuple(findings)


def _words(text: str) -> frozenset[str]:
    normalized = "".join(character if character.isalnum() else " " for character in text.lower())
    tokens = normalized.split()
    return frozenset(token for token in tokens if len(token) > 2 and token not in STOPWORDS)


def _vehicle_label(quote: QuoteSchema) -> str:
    return f"{quote.vehicle_year} {quote.vehicle_make} {quote.vehicle_model}"


def _recall_citation(quote: QuoteSchema, recall: NhtsaRecall) -> Citation:
    return Citation(
        title=f"NHTSA recall {recall.campaign}",
        url=(
            f"https://api.nhtsa.gov/recalls/recallsByVehicle?make={quote.vehicle_make}"
            f"&model={quote.vehicle_model}&modelYear={quote.vehicle_year}"
        ),
        source_type=SourceType.EXTERNAL,
    )


def _complaint_citation(quote: QuoteSchema) -> Citation:
    return Citation(
        title="NHTSA vehicle complaints",
        url=(
            f"https://api.nhtsa.gov/complaints/complaintsByVehicle?make={quote.vehicle_make}"
            f"&model={quote.vehicle_model}&modelYear={quote.vehicle_year}"
        ),
        source_type=SourceType.EXTERNAL,
    )
