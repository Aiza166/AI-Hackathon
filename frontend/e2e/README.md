# Sahara E2E journeys (Playwright)

Ten journeys from `docs/05-DEMO-SCRIPT.md` and `kissa.md`, written for **localhost only**.
Never point them at the live site: the config refuses any non-localhost `E2E_BASE_URL`.
Results of the last run: [`docs/TEST-REPORT.md`](../../docs/TEST-REPORT.md).

## Run

1. Own database (the journeys reset the demo world many times):

   ```bash
   docker compose exec db psql -U sahara -c "CREATE DATABASE sahara_e2e"
   cd backend
   set DATABASE_URL=postgresql+psycopg://sahara:sahara@localhost:5432/sahara_e2e
   alembic upgrade head && python -m app.seed
   uvicorn app.main:app --port 8010
   ```

2. Frontend dev server on 5180 with `/api` sent to 8010. `vite.config.ts` reads the proxy target from
   `VITE_PROXY_TARGET` (default `http://localhost:8000`), so no config override is needed:

   ```bash
   cd frontend
   VITE_PROXY_TARGET=http://localhost:8010 npx vite --port 5180 --strictPort
   # journey 10 (production build + service worker):
   npm run build && VITE_PROXY_TARGET=http://localhost:8010 npx vite preview --port 5181 --strictPort
   ```

   (Windows cmd: `set VITE_PROXY_TARGET=http://localhost:8010` first.)

3. Tests:

   ```bash
   cd frontend/e2e
   npm install
   npx playwright install chromium
   npm test                                  # all journeys, ~10 min
   npx playwright test j04                   # one journey
   E2E_JEV_DOWN=1 npx playwright test -g Jev # needs a backend started with TYPESAFE_BASE_URL=http://127.0.0.1:9
   ```

Screenshots go to `docs/test-screens/`; HTML report, traces, `console-errors.json` and `a11y.json`
go to `frontend/e2e/results/` (git-ignored).

## Files

| Spec | Journey |
|---|---|
| `j01-zainab-golden` | UI login, wizard with DOB + photos, AUTO_APPROVE, Listen (TTS), My data, consent take-back + 403 |
| `j02-dob-and-docs` | blank DOB, demo-button DOB, wrong DOB, edited death certificate + officer heatmap |
| `j03-helper` | family picker, locked family, acting-for banner, no PIN for helper (UI + API 403) |
| `j04-scam-shield` | fee scam + report card, genuine message, "8171" sender, borderline message |
| `j05-safeswitch` | joint flagged + cancel, wallet with wrong then right PIN, officer reject / approve |
| `j06-offline` | offline send, queued strip, sign-out confirm, synced exactly once, Idempotency-Key replay |
| `j07-staff` | officer decision + audit + chain verify (desktop), Digital Twin v2, publish, after-publish checks |
| `j08-faults` | raast timeout, identity error, Jev unreachable (opt-in) |
| `j09-a11y` | banner, RTL, 390 px overflow, tap targets, axe serious/critical, keyboard focus |
| `j10-perf` | Slow 3G first render on the production build, service worker offline reload |
| `j11-eval-judge` | Evaluation page and Judge console (admin), officer cannot open the console, 390 px fit |
| `j12-narrow-360` | Every citizen and helper screen at 360 px: no sideways scroll, Urdu RTL, tap targets >= 48 px, no CSP blocks (soft failures, all listed in `results/narrow-360.json`) |
