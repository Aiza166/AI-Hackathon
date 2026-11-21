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
| `sahara-openai-aiza` | Azure OpenAI | S0 | Second sensor in the AI cascade (gpt-4o-mini), being set up | `SECOND_SENSOR_ENDPOINT`, `SECOND_SENSOR_KEY`, `SECOND_SENSOR_DEPLOYMENT`, `SECOND_SENSOR_API_VERSION` |

S0 is pay-per-use (cents for the whole hackathon) and avoids the free tier's rate limits during judging. No commitment tiers.

## Other services

| Service | Used for | Variable |
|---|---|---|
| TypeSafe Jev (`jev-1.14.0`) | Decision model (sensor) | `TYPESAFE_API_KEY` |

## Configuration and secrets (security-fixes branch)

Names only; values live in `backend/.env` locally and in Railway variables. `ENVIRONMENT=production` turns the hardening on.

| Variable | Where | What |
|---|---|---|
| `DEMO_PIN` | backend | PIN for citizens, helper and auditor demo accounts. Locally defaults to 1234; required in production |
| `DEMO_ADMIN_PIN`, `DEMO_OFFICER_PIN` | backend | Admin / officer PINs. Required in production and must differ from 1234 and from `DEMO_PIN` (the seed refuses otherwise) |
| `DEMO_ADMIN2_PIN` | backend | Optional PIN for the second admin (00000000031) who approves rule drafts. Defaults to `DEMO_ADMIN_PIN`; in production it may not be 1234 or `DEMO_PIN` |
| `DEMO_CONSOLE_TOKEN` | backend | Judge-console token. In production the console endpoints (demo reset, faults, skip payout hold) need header `X-Demo-Console-Token` equal to it; unset = console off (404). The operator pastes it into Admin, Judge console; it stays in that browser tab (sessionStorage), never in the bundle |
| `ALLOW_DOCS` | backend | Production only: `true` exposes `/docs` and `/openapi.json` (default off) |
| `FORWARDED_ALLOW_IPS` | backend | Proxies whose `X-Forwarded-For` is trusted (comma-separated IPs/CIDRs), used by `start.sh` and the rate limiter |
| `RATELIMIT_STORAGE_URI` | backend | Rate-limit store. Empty = Redis (`REDIS_URL`) in production, memory elsewhere. The `redis` Python package is NOT in requirements yet, so limits are per process in memory |
| `MAX_BODY_BYTES` | backend | Request body cap (default 10485760) |
| `VITE_SHOW_DEMO_ACCOUNTS` | frontend build arg | `true` shows the demo persona buttons on sign-in (default false) |
| `VITE_DEMO_PIN` | frontend build arg | The public citizen demo PIN shown next to the personas. Never put an admin/officer PIN here: it is public in the bundle |
| `API_ORIGIN` | frontend runtime (nginx) | Backend public origin for the Content-Security-Policy `connect-src` |
| `REDIS_PASSWORD` | local docker compose | Redis password (default `sahara-local`); keep `REDIS_URL` in step |

Railway values to set before the demo (not confirmed yet): backend `ENVIRONMENT=production`, `DEMO_PIN`, `DEMO_ADMIN_PIN`, `DEMO_OFFICER_PIN` (and optionally `DEMO_ADMIN2_PIN`), `DEMO_CONSOLE_TOKEN` (long random), `FORWARDED_ALLOW_IPS` (Railway's proxy range, still to confirm), `ALLOW_DOCS=false`; frontend `VITE_SHOW_DEMO_ACCOUNTS=true`, `VITE_DEMO_PIN=<DEMO_PIN>`, `API_ORIGIN=<API URL>`.

### Non-owner database role for the app (recommended, not applied)

The audit log's append-only trigger can be disabled by the table owner. Run the app as a role that does not own the tables:

```sql
CREATE ROLE sahara_app LOGIN PASSWORD '<set in Railway>';
GRANT CONNECT ON DATABASE railway TO sahara_app;
GRANT USAGE ON SCHEMA public TO sahara_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO sahara_app;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_events FROM sahara_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO sahara_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO sahara_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO sahara_app;
```

Migrations keep running as the owner (separate `DATABASE_URL` for `alembic`); the API uses `sahara_app`. The chain head is also logged as `AUDIT_ANCHOR` lines so removal of the newest rows can be detected from the logs.

## If a key leaks

Regenerate it in the Azure portal (resource, Keys and Endpoint, Regenerate Key 1), then update `backend/.env` and the Railway variable. The app works without the Azure keys (fallbacks: Tesseract OCR, the phone's own voice, no second sensor).
