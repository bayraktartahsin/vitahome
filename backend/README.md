# VitaHome — backend

Agent fleet that executes medical instructions. FastAPI + ADK on Cloud Run.

See `../docs/BUILD-PLAN.md` for the full architecture.

## Layout

```
app/
  gateway/     FastAPI entrypoint · synchronous Parser (the ~1s wow moment) · fan-out
  agents/      six Pub/Sub push endpoints: reconciler scheduler pharmacist watchman coach escalator
  fleet/       ledger (idempotent step executor) · supervisor · registry · chaos
  integrations/ fhir · gcal · email · tts · veo · gemma_redact
  sim/         vitals simulator · Synthea seeding · hero patient
```

## Run locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env      # fill GEMINI_API_KEY
uvicorn app.gateway.main:app --reload --port 8080
```

## Test

```bash
pytest -q
```
