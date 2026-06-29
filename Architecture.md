# QuoteSquad
## Professional Quote Intelligence Platform

> "You shouldn't need to be an expert to know when you're being overcharged."

---

## 1. What This Is

QuoteSquad is a quote intelligence platform. You upload any professional quote — mechanic, contractor, HVAC, dental, legal, plumbing — and receive a verified, cited, confidence-scored audit of every line item, with specific dollar findings and ready-to-use negotiation artifacts.

The output is not a summary. It is a structured verdict you can act on: exact items to challenge, exact words to say, exact alternatives to call.

The system is designed so that a user can trust the output enough to walk into a negotiation with it. That trust requirement drives every architectural decision below.

---

## 2. Core Design Principles

These principles are non-negotiable. Every architecture decision traces back to one of them.

**Principle 1: The system never presents uncertainty as fact.**
Every finding carries a confidence score. Below 70% confidence, a finding is flagged as "unverified" in the UI. The system explicitly says "we don't know" when it doesn't know. No hallucinated savings numbers.

**Principle 2: Every claim has a citation.**
"Your parts are overpriced" is useless. "AutoZone retail price for Bosch BP1046N is $89. You were quoted $340. Source: AutoZone.com, accessed June 29 2026" is actionable. Every dollar figure links to an exact source.

**Principle 3: LLMs do judgment. Code does extraction.**
LLMs are not called to parse documents. They receive clean, structured, validated data and reason on it. OCR, entity extraction, schema normalization, and tool calls are deterministic code with deterministic outputs.

**Principle 4: The system degrades gracefully, not silently.**
If the parts database lookup fails, the system does not guess. It marks that item as unverified and tells the user why. Partial results are returned with explicit gaps.

**Principle 5: The data gets better with every analysis.**
Every anonymized, user-consented quote submission improves regional pricing accuracy. The knowledge base is the moat, not the model.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
│   Web App  │  Mobile App  │  Browser Extension  │  Enterprise API  │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTPS / WebSocket
┌────────────────────────────▼────────────────────────────────────────┐
│                         API GATEWAY                                 │
│   Auth (JWT/OAuth)  │  Rate Limiting  │  Request Validation         │
│   Session Management  │  PII Scrub Middleware  │  Audit Logging     │
└────────────────────────────┬────────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────────┐
│                    DOCUMENT INTELLIGENCE PIPELINE                   │
│                                                                     │
│  ┌──────────────┐  ┌────────────────┐  ┌───────────────────────┐   │
│  │  Ingestion   │  │  OCR Engine    │  │  Entity Extractor     │   │
│  │  Service     │→ │  (Tesseract +  │→ │  (rule-based NER +    │   │
│  │              │  │  Vision model) │  │  regex, NOT LLM)      │   │
│  └──────────────┘  └────────────────┘  └──────────┬────────────┘   │
│                                                   │                 │
│  ┌────────────────────────────────────────────────▼────────────┐   │
│  │  Schema Normalizer                                           │   │
│  │  Raw entities → typed QuoteSchema (Pydantic v2, validated)  │   │
│  │  Fields: line_items[], vendor, date, quote_total, zip_code  │   │
│  │  Classification: AUTO | CONTRACTOR | HVAC | DENTAL | LEGAL  │   │
│  └──────────────────────────────────┬───────────────────────────┘   │
└─────────────────────────────────────│───────────────────────────────┘
                                      │ Structured QuoteSchema
                                      │ (never raw text beyond this point)
┌─────────────────────────────────────▼───────────────────────────────┐
│                         ORCHESTRATION SERVICE                       │
│                                                                     │
│  Stateless orchestrator. Deterministic routing based on quote type. │
│  No LLM involved in routing decisions.                              │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Session State (Redis)                                       │   │
│  │  task_id, status, agent_results[], confidence_scores[]      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Agent Registry                                              │   │
│  │  Maps quote_type → [required_agents, optional_agents]       │   │
│  │  AUTO    → [LaborAgent, PartsAgent, NecessityAgent, AltAgent]│   │
│  │  MEDICAL → [ItemAgent, PriceAgent, InsuranceAgent, ErrorAgent]│   │
│  │  LEGAL   → [FeeAgent, HourAgent, MarketAgent, AltAgent]     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Task Dispatcher                                             │   │
│  │  Publishes agent tasks to queue (Temporal workflow)         │   │
│  │  Handles timeouts, retries, partial failure policy          │   │
│  └─────────────────────────────────────────────────────────────┘   │
└──────────┬──────────────┬──────────────┬──────────────┬────────────┘
           │              │              │              │
           ▼              ▼              ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  LABOR       │  │  PARTS       │  │  NECESSITY   │  │  ALTERNATIVE │
│  AGENT       │  │  AGENT       │  │  AGENT       │  │  AGENT       │
│  SERVICE     │  │  SERVICE     │  │  SERVICE     │  │  SERVICE     │
│              │  │              │  │              │  │              │
│ Own pod      │  │ Own pod      │  │ Own pod      │  │ Own pod      │
│ Own scaling  │  │ Own scaling  │  │ Own scaling  │  │ Own scaling  │
│ Own tools    │  │ Own tools    │  │ Own tools    │  │ Own tools    │
│ Own retries  │  │ Own retries  │  │ Own retries  │  │ Own retries  │
│ Own schema   │  │ Own schema   │  │ Own schema   │  │ Own schema   │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │                  │
       └─────────────────┴─────────────────┴──────────────────┘
                                    │
                         Agent results to queue
                                    │
┌───────────────────────────────────▼─────────────────────────────────┐
│                      VERIFICATION LAYER                             │
│                                                                     │
│  Cross-agent consistency checker                                    │
│  → If LaborAgent used $95/hr labor rate, PartsAgent must agree      │
│  → If same part appears in two agents, prices must reconcile        │
│                                                                     │
│  Confidence gate                                                    │
│  → Each finding has confidence score (0.0–1.0)                     │
│  → Below 0.70: flagged as "Unverified — insufficient data"          │
│  → Below 0.50: suppressed from primary output, shown in appendix   │
│                                                                     │
│  Conflict resolver                                                  │
│  → When two agents disagree, conflict is surfaced explicitly        │
│  → Synthesis agent arbitrates with source ranking                  │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────┐
│                       SYNTHESIS AGENT                               │
│                                                                     │
│  Only LLM call that produces user-facing prose.                     │
│  Input: fully structured, validated agent outputs + citations       │
│  Output: final verdict, savings summary, conflict explanations      │
│                                                                     │
│  Model: gemma-4-31b on Cerebras (reasoning_effort: medium)          │
│  Grounded strictly to structured inputs — no external knowledge     │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────┐
│                        ACTION ENGINE                                │
│                                                                     │
│  Template engine (NOT LLM) for:                                     │
│  → Challenge script (specific items, dollar amounts, legal refs)    │
│  → Email template (professional, vendor-specific)                   │
│  → Text template (casual, for individuals)                          │
│  → PDF audit report (downloadable, shareable)                       │
│  → BBB/AG complaint pre-fill (if findings exceed threshold)         │
│                                                                     │
│  LLM (gemma-4-31b) handles ONLY non-templatable sections:          │
│  → Personalized negotiation notes                                   │
│  → State-specific legal citation phrasing                           │
└───────────────────────────────────┬─────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────┐
│                       OBSERVABILITY LAYER                           │
│                                                                     │
│  OpenTelemetry traces across every service boundary                 │
│  Per-agent: token usage, latency, tool call success rate            │
│  Per-analysis: confidence distribution, savings accuracy feedback   │
│  Per-session: full replay capability for debugging                  │
│  Alerting: PagerDuty on p99 latency > 8s or agent failure > 2%     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 4. Agent Design (What an Agent Actually Is)

Each agent is a self-contained service, not a prompt. Here is the anatomy:

```
AgentService
├── input_schema         (Pydantic model — strictly typed, validated on entry)
├── output_schema        (Pydantic model — validated before leaving the agent)
├── tool_registry        (registered Tool objects with typed signatures)
├── retry_policy         (max_attempts, backoff, which errors are retryable)
├── fallback_handler     (what partial output to return if tools fail)
├── confidence_scorer    (calibrated model per agent type)
└── state_machine        (IDLE → TOOL_CALLING → REASONING → VALIDATING → DONE)
```

### Agent State Machine

```
IDLE
  │
  ▼
PARSING          ← validates input schema
  │
  ▼
TOOL_CALLING     ← deterministic lookups first (no LLM)
  │   ↑
  │   └── retry on transient failure (max 3, exponential backoff)
  ▼
DATA_ASSEMBLED   ← all tool results collected and validated
  │
  ▼
REASONING        ← LLM call with structured tool outputs as context
  │
  ▼
VALIDATING       ← output schema validation, confidence scoring
  │
  ├── confidence ≥ 0.70 → COMPLETE
  └── confidence < 0.70 → FLAGGED (returned with uncertainty markers)
```

### Tool Registry (not prompts — typed function registry)

```python
class Tool:
    name: str
    description: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    timeout_ms: int
    cache_ttl_seconds: int
    fallback: Callable | None

# Example: LaborAgent tool registry
LABOR_AGENT_TOOLS = ToolRegistry([
    Tool(
        name="lookup_mitchell_labor_time",
        input_schema=MitchellLookupInput,   # repair_type, vehicle_make, year
        output_schema=MitchellLookupOutput, # standard_hours, source_url, confidence
        timeout_ms=2000,
        cache_ttl_seconds=86400,
        fallback=lookup_chilton_labor_time
    ),
    Tool(
        name="lookup_regional_labor_rate",
        input_schema=LaborRateInput,         # zip_code, shop_type
        output_schema=LaborRateOutput,       # p25, p50, p75 rates, sample_size
        timeout_ms=1000,
        cache_ttl_seconds=3600,
        fallback=None  # returns unverified flag if unavailable
    )
])
```

### What the LLM Actually Receives

The LLM never receives raw document text. It receives structured data assembled by tool calls:

```json
{
  "line_item": {
    "description": "Front brake rotor replacement (pair)",
    "quoted_hours": 3.5,
    "quoted_labor_cost": 332.50,
    "labor_rate_used": 95.00
  },
  "tool_results": {
    "mitchell_standard_hours": {
      "value": 1.2,
      "confidence": 0.94,
      "source": "Mitchell ProDemand — 2019 Toyota Camry 2.5L front rotor R&R",
      "source_url": "..."
    },
    "regional_labor_rate": {
      "p50_rate": 92.00,
      "p75_rate": 108.00,
      "zip_code": "90210",
      "sample_size": 847,
      "data_freshness_days": 14
    }
  }
}
```

The LLM's job is to reason: is 3.5 quoted hours vs. 1.2 standard hours explainable by the vehicle, condition notes, or is it an overcharge? That judgment requires language understanding. The math does not.

---

## 5. Knowledge Infrastructure (The Moat)

The model is a commodity. The data is the moat.

### Pricing Knowledge Base

```
┌─────────────────────────────────────────────────────┐
│              KNOWLEDGE BASE SERVICES                │
│                                                     │
│  Labor Time DB          Parts Price DB              │
│  ─────────────          ───────────────             │
│  Mitchell (licensed)    eBay Motors (scraped daily) │
│  Chilton (licensed)     RockAuto (scraped daily)    │
│  RSMeans (construction) AutoZone (scraped daily)    │
│  ADA fee schedules      Home Depot (licensed API)   │
│                         Amazon (Product API)        │
│                                                     │
│  Regional Pricing DB    Maintenance Schedule DB     │
│  ────────────────────   ───────────────────────     │
│  User-submitted quotes  OEM service manuals         │
│  (anonymized, consented)(scraped, 45 makes)         │
│  Aggregated by zip+type Indexed by make/model/year  │
│  Updated continuously   Updated on manufacturer     │
│                         bulletin releases           │
│                                                     │
│  Vendor Intelligence DB Regulatory DB               │
│  ──────────────────────  ───────────────            │
│  Yelp ratings history   State tenant law (leases)  │
│  Google reviews signals State consumer law         │
│  BBB complaint history  State AG rulings           │
│  License verification   Medicare fee schedules     │
└─────────────────────────────────────────────────────┘
```

### Data Freshness Policy

| Data Type | Acceptable Staleness | Refresh Strategy |
|---|---|---|
| Parts retail prices | 24 hours | Nightly scrape pipeline |
| Regional labor rates | 7 days | Weekly aggregate from submissions |
| Yelp ratings | 48 hours | Yelp Fusion API poll |
| Maintenance schedules | 30 days | Manual review + OEM bulletin monitoring |
| State regulations | 7 days | Legal feed subscription |
| User-submitted quote data | Real-time | Ingested on submission |

### The Flywheel

Every user who submits a quote and reports outcome ("I challenged item 3 and got $200 off") feeds back into:

1. Confidence model calibration — were we right?
2. Regional pricing accuracy — is this zip code's p50 labor rate correct?
3. Vendor intelligence — this shop has 12 overcharge flags this month
4. Negotiation success rate by script type

After 100,000 analyses, the confidence scores are empirically calibrated. After 1,000,000, the regional pricing database is more accurate than any licensed data source because it reflects what shops actually charge, not what guides say they should.

---

## 6. Trust and Verification Layer

This is what separates a useful tool from a trusted one.

### Confidence Scoring

Each finding is scored on three dimensions:

```
source_quality_score    (0–1): is the source authoritative and fresh?
match_confidence        (0–1): how precisely did the item match the database?
sample_size_weight      (0–1): how many similar cases support this finding?

confidence = weighted_average(source_quality, match_confidence, sample_size_weight)
```

UI treatment by confidence level:

| Confidence | Treatment |
|---|---|
| ≥ 0.85 | Solid red/green card. Dollar figure shown. Include in challenge script. |
| 0.70–0.84 | Card with caveat: "Based on 23 similar repairs in your area." Include in script with qualifier. |
| 0.50–0.69 | Greyed card: "Possibly inflated — insufficient local data to confirm." Not in script. |
| < 0.50 | Not shown in primary output. Available in detailed view on request. |

### Cross-Agent Consistency Check

Before synthesis, the verification service checks:

- Labor rate used by LaborAgent matches regional rate in database
- Part numbers referenced by PartsAgent match the vehicle year/make/model
- Necessity flags don't contradict each other (can't flag flush as unnecessary AND recommend it)
- Alternative shops are actually licensed for the quote type in that state

Conflicts are surfaced as explicit notes, not silently resolved.

### What the System Refuses to Do

- Present a savings figure it cannot source
- Include a finding in the challenge script unless confidence ≥ 0.70
- Make legal claims without citing exact statute
- Recommend an alternative shop without verifying it is currently open and licensed

---

## 7. Security and Compliance

Users upload financial documents, medical bills, and legal agreements. This is not optional.

### Data Handling

- All uploaded documents encrypted at rest (AES-256) and in transit (TLS 1.3)
- Documents are processed in-memory — never written to persistent storage in raw form
- After analysis completes, raw document is deleted within 24 hours (configurable per user)
- Anonymized, consented quote data stored separately from PII

### PII Scrub Middleware

Runs at the API gateway before any document reaches the processing pipeline:

- Detects and redacts: name, address, phone, email, SSN, insurance member ID, VIN
- Redaction is logged but redacted values are not logged
- External API calls (Yelp, parts databases) never receive PII

### Compliance Path

- SOC 2 Type II: target within 12 months of launch
- HIPAA considerations: medical bill track requires BAA with any processing vendor
- GDPR / CCPA: right to deletion implemented from day one — user can delete all data in one click
- No training on user data without explicit opt-in (separate, paid tier: "Help improve QuoteSquad")

---

## 8. Infrastructure and Scalability

### Services

```
quotesquad-api          FastAPI — request entry, auth, session management
quotesquad-ingest       Document processing pipeline — OCR, extraction, classification
quotesquad-orchestrator Temporal worker — workflow management, agent dispatch
quotesquad-labor        Labor agent service
quotesquad-parts        Parts agent service
quotesquad-necessity    Necessity agent service
quotesquad-alternative  Alternative finder service
quotesquad-verify       Verification and consistency service
quotesquad-synthesis    Synthesis agent — final LLM call
quotesquad-action       Action engine — script and template generation
quotesquad-knowledge    Knowledge base query service (internal only)
quotesquad-feedback     Feedback ingestion and model calibration
```

### Infrastructure Stack

| Component | Technology | Reason |
|---|---|---|
| Container orchestration | Kubernetes (EKS) | Per-agent independent scaling |
| Workflow orchestration | Temporal | Durable execution, full replay, agent failure handling |
| Message queue | Redis Streams | Agent result collection, low latency |
| Primary database | PostgreSQL (RDS) | Structured knowledge base, ACID guarantees |
| Vector search | pgvector | Semantic part/service matching |
| Cache | Redis | Hot pricing data, session state |
| Object storage | S3 | Raw document staging (24h TTL) |
| LLM inference | Cerebras (Gemma 4 31B) | Speed-critical for agent reasoning calls |
| OCR | Tesseract + Gemma 4 vision | Tesseract for clean docs, vision for photos |
| Observability | OpenTelemetry + Grafana + Jaeger | Full distributed tracing |
| Secrets | AWS Secrets Manager | No hardcoded credentials anywhere |
| CI/CD | GitHub Actions + ArgoCD | GitOps deploy model |

### Scaling Model

Each agent service scales independently based on its own queue depth. A spike in automotive quote submissions scales the LaborAgent and PartsAgent pods without touching the NecessityAgent or AlternativeAgent.

The orchestrator is stateless — session state lives in Redis, so orchestrator pods scale freely.

The knowledge base query service has a read replica per region. Pricing lookups never hit the primary database.

### SLAs

| Metric | Target |
|---|---|
| Time to first agent result | < 1.5s |
| Time to complete analysis | < 5s (p95) |
| System uptime | 99.9% |
| Agent failure rate | < 0.5% |
| Max document size | 50MB |
| Supported formats | PDF, JPG, PNG, HEIC, WebP |

---

## 9. Business Model

### Consumer (B2C)

| Tier | Price | Includes |
|---|---|---|
| Free | $0 | 2 analyses/month, basic scorecard |
| Plus | $9.99/month | Unlimited analyses, full citation trail, PDF report, challenge script, email template |
| Pro | $24.99/month | Everything in Plus, negotiation playbook, outcome tracking, priority support |

### Enterprise (B2B)

| Customer | Use Case | Pricing |
|---|---|---|
| Insurance adjusters | Audit repair estimates before approving claims | Per-seat SaaS |
| Fleet management companies | Standardize maintenance cost benchmarks across 100s of vehicles | Volume API |
| Home warranty companies | Validate contractor quotes before authorization | Per-claim fee |
| Consumer protection orgs | Identify systematic overcharging patterns | Non-profit licensing |
| Credit unions / banks | Member benefit — free analyses for account holders | White-label API |

### Revenue Defense

The enterprise contracts are the defensible revenue. A home warranty company processing 50,000 claims/month at $2/claim is $1.2M ARR from one customer. They will not switch providers because the knowledge base calibrated to their specific contractor network is not portable.

---

## 10. What This Is Not

- Not a chatbot. No conversational interface in the core product.
- Not a general AI assistant. It does one thing with high accuracy.
- Not dependent on any single LLM. The model is a component. The architecture is the product.
- Not a dashboard. The output is an artifact you take out of the app and use.

The product is the quality of the judgment. If we are wrong about a finding, a user walks into a negotiation with bad information. That is worse than no information. Every decision above exists to prevent that.

---

## 11. Roadmap

### Phase 1 — Foundation (Months 1–3)
Automotive quotes only. Core 4-agent architecture. Consumer web app. Mitchell + eBay Motors + Yelp integrations. Confidence scoring v1.

### Phase 2 — Accuracy (Months 4–6)
Feedback loop live. Confidence model calibration from real outcomes. Regional pricing database starts building from user submissions. Contractor quotes added (RSMeans + Home Depot integration).

### Phase 3 — Enterprise (Months 7–12)
Insurance adjuster API. Fleet management dashboard. White-label product. HIPAA-adjacent track for medical bills (requires legal review). SOC 2 audit begins.

### Phase 4 — Moat (Months 13–24)
Proprietary pricing database surpasses licensed sources in accuracy for covered zip codes. Vendor intelligence layer: shops with repeat overcharge patterns flagged proactively. Outcome-based confidence scoring: we know our track record by category, by region, by shop type.

---

*QuoteSquad — Professional Quote Intelligence*
*Model: gemma-4-31b | Inference: Cerebras | Architecture: multi-agent, citation-grounded, confidence-scored*
