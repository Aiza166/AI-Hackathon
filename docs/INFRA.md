# Infrastructure (where things run)

Names only. Keys and secrets are never written here or in git: they live in `backend/.env` (git-ignored) and in Railway variables.

## Railway (app hosting)

| Service | What | Notes |
|---|---|---|
| `AI-Hackathon` | FastAPI backend (`/backend`, Dockerfile) | `start.sh`: `alembic upgrade head`, seed if empty or seed version changed, then uvicorn |
| `confident-growth` | Frontend PWA (`/frontend`, nginx) | Built with `VITE_API_BASE` |
| `Postgres` | Database | Railway-managed |

Project: `charming-youth`. Auto-deploys on every push to `main`.

- App: https://confident-growth-production-1cfebeef.up.railway.app
- API: https://ai-hackathon-production-31dd3038.up.railway.app (`/readyz` shows DB and Jev status)

## Azure (Azure for Students subscription)

All in resource group **`sahara-rg`**, region **UAE North** (`uaenorth`). The student subscription only allows a few regions (UAE North, Korea Central, Poland Central, Malaysia West and others; East US and Southeast Asia are blocked).

| Resource | Service | Tier | Used for | Variables |
|---|---|---|---|---|
| `sahara-speech-aiza` | Speech | S0 | Urdu/English voice (`ur-PK-UzmaNeural`), speech to text | `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` |
| `sahara-docs-aiza` | Document Intelligence | S0 | OCR of uploaded documents (prebuilt-read) | `AZURE_DOCINTEL_ENDPOINT`, `AZURE_DOCINTEL_KEY` |
| `sahara-openai-aiza` | Azure OpenAI | S0 | Second sensor in the AI cascade: deployment `gpt-5-mini` (model gpt-5-mini 2025-08-07, GlobalStandard, API version 2025-04-01-preview); gpt-4o-mini is deprecating and gpt-5.4-mini had no student quota | `SECOND_SENSOR_ENDPOINT`, `SECOND_SENSOR_KEY`, `SECOND_SENSOR_DEPLOYMENT`, `SECOND_SENSOR_API_VERSION` |

S0 is pay-per-use (cents for the whole hackathon) and avoids the free tier's rate limits during judging. No commitment tiers.

## Other services

| Service | Used for | Variable |
|---|---|---|
| TypeSafe Jev (`jev-1.14.0`) | Decision model (sensor) | `TYPESAFE_API_KEY` |

## Monitoring

### Sentry (errors)

Organisation `na-pz5`, EU data region (ingest host `*.ingest.de.sentry.io`). Two projects:

| Project | Where the DSN lives | How it is used |
|---|---|---|
| `sahara-backend` | `SENTRY_DSN` in `backend/.env` and on Railway service `AI-Hackathon` | `app/core/monitoring.py`, started in `create_app()` only when the DSN is set. Environment: `SENTRY_ENVIRONMENT`, else `production` on Railway, else `ENVIRONMENT`. Release: `sahara-backend@<RAILWAY_GIT_COMMIT_SHA>`. 10% of requests traced |
| `sahara-frontend` | `VITE_SENTRY_DSN` on Railway service `confident-growth` (Dockerfile build arg; a browser DSN is public by design) | `src/lib/monitoring.ts` loads the SDK chunk (~30 KB gzipped, own chunk, not precached) after first paint, only when the DSN was set at build time. Error boundary reports render crashes. No replays, no tracing |

What is scrubbed before anything leaves (backend and browser use the same rules, unit-tested):

- request bodies, cookies and server env are dropped entirely; no frame locals, no SQL values
- the user block is emptied (the browser keeps only the role, e.g. `citizen`)
- keys that look secret are replaced by `[Filtered]`: pin, password, token, authorization, api key, cookie, session, refresh, otp, iban, cnic, phone
- in every remaining string, URL and query string: CNICs and IBANs keep only the last 4 characters (same helper as the audit trail), phone numbers keep the last 2 digits, `pin 1234` becomes `pin ****`, JWTs, bearer tokens and `sk_` API keys are replaced

Demo: sign in as admin, `POST /api/v1/admin/sentry-test` (audited as `SENTRY_TEST_TRIGGERED`, returns a generic 500; 503 when Sentry is off). The issue shows in `sahara-backend` with the mock CNIC in the message masked.

### Codecov (test coverage)

CI uploads `backend/coverage.xml` (pytest-cov, flag `backend`) and `frontend/lcov.info` (Node test runner coverage, flag `frontend`) with the `CODECOV_TOKEN` repository secret. The upload is skipped when the secret is missing and never fails CI; `codecov.yml` makes the status checks informational. Dashboard: https://app.codecov.io/gh/Aiza166/AI-Hackathon

## If a key leaks

Regenerate it in the Azure portal (resource, Keys and Endpoint, Regenerate Key 1), then update `backend/.env` and the Railway variable. A Sentry DSN only allows sending events: if one is abused, create a new client key in the Sentry project (Settings, Client Keys), disable the old one and update the Railway variable (the frontend needs a redeploy because the DSN is built in). The app works without the Azure keys (fallbacks: Tesseract OCR, the phone's own voice, no second sensor).
