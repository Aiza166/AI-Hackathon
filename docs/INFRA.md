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

## If a key leaks

Regenerate it in the Azure portal (resource, Keys and Endpoint, Regenerate Key 1), then update `backend/.env` and the Railway variable. The app works without the Azure keys (fallbacks: Tesseract OCR, the phone's own voice, no second sensor).
