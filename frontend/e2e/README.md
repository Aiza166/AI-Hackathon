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

2. Frontend dev server on 5180 with `/api` sent to 8010. `vite.config.ts` hardcodes `:8000`, so use a
   local, uncommitted override `frontend/vite.e2e.config.ts`:

   ```ts
   import { mergeConfig } from 'vite'
   import base from './vite.config'
   const proxy = { '/api': 'http://localhost:8010' }
   export default mergeConfig(base, {
     server: { port: 5180, strictPort: true, proxy },
     preview: { port: 5181, strictPort: true, proxy },
   })
   ```

   `npx vite --config vite.e2e.config.ts` (dev, 5180). For journey 10 also
   `npm run build && npx vite preview --config vite.e2e.config.ts` (production build + service worker, 5181).

3. Tests:

   ```bash
   cd frontend/e2e
   npm install
   npx playwright install chromium
   npm test                                  # all journeys, ~10 min (login limit is 10/min: the helper waits)
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
