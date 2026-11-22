# Sahara frontend

React 19 + TypeScript + Vite offline-first PWA. Citizen screens are Urdu first (Sindhi and Punjabi on request), with icons and a Listen button on every step. Staff screens (officer, admin, auditor) are lazy-loaded so the citizen shell stays small.

```bash
npm install
npm run dev          # http://localhost:5173, proxies /api to http://localhost:8000
npm run build        # production build; the citizen JavaScript budget is 100 KB gzipped
npm run test:unit    # unit tests (Node test runner)
```

- `src/api/`: fetch client and types that mirror `backend/app/schemas`
- `src/pages/`: Login, ClaimWizard, CaseResult, CitizenHome, OfficerHome, AdminHome, AuditorHome, ScamShield, SafeSwitch, Evaluation, JudgeConsole
- `src/lib/`: offline outbox (IndexedDB), speech playback, language choice, sharing
- `src/i18n/`: Sindhi and Punjabi text packs (machine-assisted, to be reviewed) and the voice clip list
- `e2e/`: Playwright journeys, see [e2e/README.md](e2e/README.md)

See the [root README](../README.md) for the whole project.
