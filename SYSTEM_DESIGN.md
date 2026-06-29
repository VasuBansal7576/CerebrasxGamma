# QuoteSquad System Design

This file describes the system that is implemented in this repository. The larger product ambition lives in `Architecture.md`; this document is the reviewer-facing map for the current build.

## Goals

QuoteSquad audits repair, contractor, and service quotes. It turns pasted text or uploaded documents into a structured analysis with line items, confidence-gated findings, citations, negotiation guidance, and a downloadable PDF report.

The core design rule is explicit uncertainty: missing providers, blocked public data, weak evidence, OCR limits, and credential gaps are returned as provider gaps instead of hidden behind fake estimates.

## Runtime Shape

```text
Browser / API client
        |
        v
FastAPI app
  - web routes: paste/upload quote, report page, enterprise page, PDF
  - API routes: analyses, feedback, readiness, vendor intelligence, compliance
        |
        v
Service pipeline
  - redact PII
  - extract quote schema
  - run deterministic agents
  - run public-data agents
  - verify confidence and conflicts
  - synthesize negotiation guidance
  - persist analysis
        |
        v
SQLAlchemy async database
  - SQLite by default
  - Postgres-ready via QUOTESQUAD_DATABASE_URL
```

## Main Modules

| Module | Responsibility |
| --- | --- |
| `src/quotesquad/main.py` | FastAPI app factory, static files, route registration, startup database init. |
| `src/quotesquad/routers/web.py` | Server-rendered UX for quote submission, reports, enterprise view, and PDF download. |
| `src/quotesquad/routers/api.py` | JSON API for analyses, feedback, calibration, vendor intelligence, readiness, compliance, and deletion. |
| `src/quotesquad/service.py` | End-to-end analysis orchestration. |
| `src/quotesquad/document.py` | Upload extraction for text, PDF, image OCR fallback, and extraction gaps. |
| `src/quotesquad/pii.py` | PII redaction before extraction and analysis. |
| `src/quotesquad/agents.py` | Deterministic labor, parts, contractor, necessity, and alternatives agents. |
| `src/quotesquad/public_data.py` | No-key NHTSA recall/complaint enrichment plus eBay public-web agent orchestration. |
| `src/quotesquad/market_web.py` | Best-effort public eBay price parsing with explicit blocked-state gaps. |
| `src/quotesquad/verification.py` | Confidence gate and conflict extraction. |
| `src/quotesquad/synthesis.py` | Deterministic synthesis plus optional Cerebras JSON synthesis when configured. |
| `src/quotesquad/repository.py` | Persistence, feedback loop, calibration, regional benchmarks, vendor intelligence, white-label settings. |
| `src/quotesquad/readiness.py` | Provider and infrastructure readiness reporting. |
| `src/quotesquad/schemas.py` | Pydantic API/domain contracts. |

## Request Lifecycle

1. A user submits quote text or uploads a document from `/` or calls `POST /api/analyses`.
2. Uploads pass through `document.py`. Text and text PDFs are extracted locally. Images use local Tesseract when available and return an OCR gap when it is not.
3. The input is redacted by `pii.py`.
4. `service.py` extracts a `QuoteSchema`, including line items, totals, zip code, and vehicle hints when present.
5. Deterministic agents inspect line items for labor, parts, contractor, necessity, and alternative recommendation issues.
6. Public-data agents add NHTSA recall/complaint findings for detected vehicles and best-effort eBay public-web parts pricing. Blocked public web returns a provider gap.
7. `verification.py` keeps confidence, conflict, and source quality visible.
8. `synthesis.py` creates a deterministic summary. If `QUOTESQUAD_CEREBRAS_API_KEY` exists, Cerebras can replace the summary and negotiation notes while staying grounded in structured findings.
9. `repository.py` stores the full `AnalysisRead` JSON result and optional feedback/calibration rows.
10. The user receives a report page, JSON response, and optional PDF export.

## Data Model

The database is intentionally simple:

- `AnalysisRecord`: immutable stored analysis payload.
- `FeedbackRecord`: outcome and negotiated savings for calibration.
- `PricingObservationRecord`: consented regional/vendor observations.
- `WhiteLabelRecord`: organization display settings.

SQLite is the default for local development and demos. Production deployments should set `QUOTESQUAD_DATABASE_URL` to an async Postgres URL. `asyncpg` is already included.

## External Providers

| Provider | Current behavior |
| --- | --- |
| Cerebras | Optional live synthesis. Missing key or failures fall back to deterministic synthesis with a provider gap. |
| NHTSA | No-key public recall and complaint lookups for detected vehicle quotes. |
| eBay public web | Best-effort public price parsing. Blocked/captcha/parse failures are returned as gaps. |
| Tesseract | Optional local OCR for image uploads. No cloud OCR key required. |
| Mitchell, Chilton, RSMeans, Home Depot, Yelp, BBB | Readiness placeholders only. The app does not fake these integrations. |

## Security and Privacy Boundaries

- `.env` is ignored and should hold local secrets only.
- `.env.example` documents supported configuration without secrets.
- Optional API key enforcement uses `QUOTESQUAD_API_KEY` and `X-QuoteSquad-Key`.
- Quote text is PII-scrubbed before analysis.
- Delete support exists through `DELETE /api/analyses/{analysis_id}`.
- Provider gaps make missing credentials and failed provider calls visible.

## Deployment Shape

The repository includes:

- `Dockerfile` for containerized app runtime.
- `docker-compose.yml` for local Postgres/Redis-style production dependencies.
- `Makefile` commands for dev and verification.
- `pyproject.toml` and `uv.lock` for reproducible Python dependencies.

Production should add managed Postgres, Redis or workflow infrastructure if needed, object storage for durable uploads/reports, OpenTelemetry export, a secrets manager, and provider credentials. The app exposes `/api/infra/readiness` and `/api/providers/status` so those gaps are inspectable.

## Verification

Current local verification:

```bash
uv run ruff check src tests --no-cache
TMPDIR=$PWD/data uv run basedpyright
TMPDIR=$PWD/data uv run pytest -q
```

The test suite covers the deterministic pipeline, feedback/calibration behavior, provider readiness, NHTSA-style public data, eBay blocked-state handling, and Cerebras response-shape tolerance.

## Known Product Gaps

These are intentionally not papered over:

- Reliable live parts pricing still needs an official provider or stable ingestion path.
- Paid repair and contractor catalogs are not integrated without credentials.
- Alternative vendor recommendations are currently heuristic/readiness-level, not a full marketplace/ranking system.
- Cloud infrastructure is deployable but not provisioned in this repo.
- Mobile app, browser extension, SOC 2, HIPAA, and legal certification are not implemented by code alone.
