# QuoteSquad

Production core for the architecture in `Architecture.md`: upload or paste a quote, get a structured confidence-scored audit, citations, negotiation scripts, and a downloadable report.

## What is implemented

- FastAPI web app and JSON API.
- PII scrub before extraction.
- Deterministic quote extraction for text and text PDFs.
- Optional local Tesseract OCR for image uploads, with explicit gaps when unavailable.
- No-key NHTSA recall and complaint context for detected vehicle quotes.
- Best-effort eBay public-web parts price checks, with explicit gaps when blocked.
- Multi-agent audit pipeline: labor, parts, contractor, necessity, alternatives.
- Verification gate with confidence bands and conflict notes.
- Cerebras synthesis boundary, disabled until `QUOTESQUAD_CEREBRAS_API_KEY` is set.
- SQLite persistence by default; set `QUOTESQUAD_DATABASE_URL` for another SQLAlchemy async database URL.
- PDF audit report and action templates.
- Feedback loop, outcome calibration, regional pricing observations, contractor quote support.
- Enterprise audit API, fleet/vendor intelligence, white-label config, compliance controls, deletion.
- Provider and infrastructure readiness APIs for credential and production-rollout handoff.

## Run locally

```bash
uv sync
cp .env.example .env
make dev
```

Open `http://localhost:8000`.

## API

```bash
curl -X POST http://localhost:8000/api/analyses \
  -H 'content-type: application/json' \
  -d '{"quote_text":"Brake rotors 3.5 hours labor $525\nFront brake rotors $340\nTotal $865","zip_code":"90210"}'
```

If `QUOTESQUAD_API_KEY` is set, pass it as `X-QuoteSquad-Key`.

## Roadmap phase surfaces

```bash
# Phase 2: feedback, calibration, regional pricing
curl -X POST http://localhost:8000/api/analyses/{id}/feedback \
  -H 'content-type: application/json' \
  -d '{"outcome":"won_discount","negotiated_savings":{"amount":"200.00"}}'
curl http://localhost:8000/api/calibration
curl http://localhost:8000/api/regional/90210

# Phase 3: enterprise and white-label
curl -X POST http://localhost:8000/api/enterprise/audits \
  -H 'content-type: application/json' \
  -d '{"organization_id":"fleetco","external_ref":"claim-1","use_case":"fleet","quote_text":"Drywall repair $700","zip_code":"78701"}'
curl http://localhost:8000/enterprise
curl -X PUT http://localhost:8000/api/white-label/fleetco \
  -H 'content-type: application/json' \
  -d '{"organization_id":"fleetco","display_name":"Fleet Quote Audit"}'

# Phase 4: moat
curl http://localhost:8000/api/vendors/intelligence
curl http://localhost:8000/api/compliance/controls

# Production readiness handoff
curl http://localhost:8000/api/providers/status
curl http://localhost:8000/api/infra/readiness
```

## Credentials

Add Cerebras after the build:

```env
QUOTESQUAD_CEREBRAS_API_KEY=...
QUOTESQUAD_CEREBRAS_MODEL=gemma-4-31b
QUOTESQUAD_NHTSA_BASE_URL=https://api.nhtsa.gov
QUOTESQUAD_MITCHELL_API_KEY=...
QUOTESQUAD_CHILTON_API_KEY=...
QUOTESQUAD_EBAY_API_KEY=...
QUOTESQUAD_YELP_API_KEY=...
QUOTESQUAD_RSMEANS_API_KEY=...
QUOTESQUAD_HOME_DEPOT_API_KEY=...
QUOTESQUAD_BBB_API_KEY=...
QUOTESQUAD_VISION_OCR_API_KEY=...
QUOTESQUAD_REDIS_URL=...
QUOTESQUAD_TEMPORAL_ADDRESS=...
QUOTESQUAD_OBJECT_STORAGE_BUCKET=...
QUOTESQUAD_OTEL_EXPORTER_OTLP_ENDPOINT=...
QUOTESQUAD_PAGERDUTY_ROUTING_KEY=...
QUOTESQUAD_AWS_SECRETS_NAME=...
```

Until then the app keeps working locally, uses deterministic fallbacks where safe, and marks missing providers as explicit gaps.

## Checks

```bash
make check
```
