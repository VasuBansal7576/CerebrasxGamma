from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class QuoteType(StrEnum):
    AUTO = "auto"
    CONTRACTOR = "contractor"
    HVAC = "hvac"
    DENTAL = "dental"
    LEGAL = "legal"
    UNKNOWN = "unknown"


class LineItemKind(StrEnum):
    LABOR = "labor"
    PART = "part"
    SERVICE = "service"
    FEE = "fee"
    UNKNOWN = "unknown"


class ConfidenceStatus(StrEnum):
    VERIFIED = "verified"
    CAVEATED = "caveated"
    UNVERIFIED = "unverified"
    SUPPRESSED = "suppressed"


class AnalysisStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class SourceType(StrEnum):
    USER_DOCUMENT = "user_document"
    SEED = "seed"
    EXTERNAL = "external"
    CONFIGURATION = "configuration"


class FeedbackOutcome(StrEnum):
    WON_DISCOUNT = "won_discount"
    VENDOR_JUSTIFIED = "vendor_justified"
    NO_CHANGE = "no_change"
    WRONG = "wrong"


class EnterpriseUseCase(StrEnum):
    INSURANCE = "insurance"
    FLEET = "fleet"
    HOME_WARRANTY = "home_warranty"
    CONSUMER_PROTECTION = "consumer_protection"
    WHITE_LABEL = "white_label"


class MoneyModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    amount: Decimal = Field(ge=Decimal("0"))
    currency: Literal["USD"] = "USD"

    @field_serializer("amount")
    def serialize_amount(self, amount: Decimal) -> str:
        return f"{amount.quantize(Decimal('0.01'))}"


class Citation(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    url: str
    source_type: SourceType
    accessed_at: date = Field(default_factory=lambda: datetime.now(UTC).date())


class Redaction(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str
    count: int = Field(ge=1)


class ProviderGap(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    reason: str
    blocks: str


class LineItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    index: int = Field(ge=0)
    description: str
    kind: LineItemKind
    quantity: Decimal = Field(default=Decimal("1"), gt=Decimal("0"))
    total: MoneyModel
    quoted_hours: Decimal | None = Field(default=None, ge=Decimal("0"))
    source_line: str


class QuoteSchema(BaseModel):
    model_config = ConfigDict(frozen=True)

    quote_type: QuoteType
    vendor: str | None = None
    quote_date: date | None = None
    quote_total: MoneyModel | None = None
    zip_code: str | None = None
    vehicle_year: int | None = Field(default=None, ge=1981, le=2035)
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    line_items: tuple[LineItem, ...]
    redactions: tuple[Redaction, ...] = ()
    extraction_gaps: tuple[ProviderGap, ...] = ()


class AgentFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    agent: str
    line_item_index: int | None = None
    category: str
    title: str
    finding: str
    quoted: MoneyModel | None = None
    benchmark: MoneyModel | None = None
    delta: MoneyModel | None = None
    confidence: float = Field(ge=0, le=1)
    status: ConfidenceStatus
    citations: tuple[Citation, ...]


class AgentResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    agent: str
    findings: tuple[AgentFinding, ...]
    gaps: tuple[ProviderGap, ...] = ()


class VerifiedAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True)

    findings: tuple[AgentFinding, ...]
    conflicts: tuple[str, ...] = ()
    gaps: tuple[ProviderGap, ...] = ()


class ActionPack(BaseModel):
    model_config = ConfigDict(frozen=True)

    challenge_script: str
    email_template: str
    text_template: str
    complaint_note: str | None = None


class Synthesis(BaseModel):
    model_config = ConfigDict(frozen=True)

    verdict: str
    summary: str
    savings_low: MoneyModel
    savings_high: MoneyModel
    negotiation_notes: tuple[str, ...]
    provider_gaps: tuple[ProviderGap, ...] = ()


class AnalysisRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    status: AnalysisStatus
    created_at: datetime
    quote: QuoteSchema
    findings: tuple[AgentFinding, ...]
    conflicts: tuple[str, ...]
    gaps: tuple[ProviderGap, ...]
    synthesis: Synthesis
    actions: ActionPack


class AnalyzeQuoteRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    quote_text: str = Field(min_length=1)
    zip_code: str | None = Field(default=None, min_length=5, max_length=10)
    consent_to_learn: bool = False


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    outcome: FeedbackOutcome
    negotiated_savings: MoneyModel = Field(default_factory=lambda: MoneyModel(amount=Decimal("0")))
    notes: str | None = None


class FeedbackRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    analysis_id: str
    outcome: FeedbackOutcome
    negotiated_savings: MoneyModel
    calibrated_categories: tuple[str, ...]


class RegionalBenchmarkRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    quote_type: QuoteType
    zip_prefix: str
    category: str
    sample_size: int
    average_amount: MoneyModel


class EnterpriseAuditRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    organization_id: str = Field(min_length=1)
    external_ref: str = Field(min_length=1)
    use_case: EnterpriseUseCase
    quote_text: str = Field(min_length=1)
    zip_code: str | None = Field(default=None, min_length=5, max_length=10)


class EnterpriseAuditRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    organization_id: str
    external_ref: str
    use_case: EnterpriseUseCase
    analysis: AnalysisRead


class WhiteLabelConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    organization_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    support_email: str | None = None
    primary_color: str = "#1D6B4F"


class CalibrationRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: str
    sample_size: int
    success_rate: float = Field(ge=0, le=1)
    confidence_multiplier: float = Field(ge=0, le=1.2)


class VendorIntelligenceRead(BaseModel):
    model_config = ConfigDict(frozen=True)

    vendor: str
    analyses: int
    flagged_findings: int
    total_potential_delta: MoneyModel
    repeat_flag: bool


class ComplianceControl(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: str
    status: str
    evidence: str
