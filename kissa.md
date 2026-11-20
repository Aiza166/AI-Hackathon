# Kissa: start here

> Your personal task list. Aiza (and Claude) keep this updated. Tick boxes as you finish and push.
> Last updated: Sat 21 Nov ~04:00. **Phase 1 is built** (backend + a first version of your screens). Read section 0 first.

## 0. What changed overnight (read first)

- The backend for Phase 1 is done and tested (83 tests). Run it with the steps in [docs/STATUS.md](docs/STATUS.md).
- Claude built **first versions** of these screens so the golden path works end to end: `src/pages/Login.tsx`, `ClaimWizard.tsx`, `CaseResult.tsx`, `CitizenHome.tsx` (incl. Helper Mode picker), `OfficerHome.tsx`, `AuditorHome.tsx`. They use emoji as icons and plain CSS. **They are yours now**: improve the design, swap emoji for real pictograms, make them feel right on a cheap phone.
- API types are hand-written in `src/api/types.ts`; replace with generated ones (`npx openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.ts`).
- So your Phase 1 boxes below are mostly ticked; jump to Phase 2.

## 1. What we are building (2 minute read)

**Sahara**: a prototype platform that helps widows claim their late husband's pension safely, even when they can't read, have weak signal, records spell names differently, and scammers or fake heirs target them.

Read in this order: [README](README.md), then [docs/01-IDEA.md](docs/01-IDEA.md) (the story), then [docs/05-DEMO-SCRIPT.md](docs/05-DEMO-SCRIPT.md) (what judges will see). Skim [docs/04-BUILD-PLAN.md](docs/04-BUILD-PLAN.md) for the timeline.

## 2. Your streams

You own **Stream C (Frontend PWA)** and **Stream D (Demo & quality)**. Aiza owns A (platform/security) and B (decision engine/AI). Shout if you'd rather swap.

## 3. Setup (about 20 minutes)

1. Clone: `git clone https://github.com/Aiza166/AI-Hackathon.git` and open it.
2. Install: Node 20+, Python 3.12, Docker Desktop, Git.
3. Frontend:
   ```bash
   cd frontend
   npm install
   npm run dev        # http://localhost:5173
   ```
4. Backend (optional for you at first):
   ```bash
   docker compose up -d                 # Postgres + Redis, from repo root
   cd backend
   python -m venv .venv
   .venv\Scripts\activate               # Windows
   pip install -r requirements.txt
   copy .env.example .env               # ask Aiza for any keys; never commit .env
   pytest
   uvicorn app.main:app --reload        # http://localhost:8000/docs
   ```
5. Claude Code + ECC (the toolkit we use): clone `https://github.com/affaan-m/ECC` **outside** this repo, then from the folder that contains `AI-Hackathon` run:
   `node ECC/scripts/install-apply.js --target claude-project --profile core --enable-hooks`
   Then open Claude Code in that folder. Useful: `/plan`, `tdd-workflow`, `/code-review`, agents `react-reviewer`, `a11y-architect`, `e2e-runner`.

## 4. Your tasks now

### Phase 0 (tonight / first thing)
- [ ] Do the setup above; run the frontend; push one small commit (e.g., your name in this file) so we know access works.
- [ ] Read the 3 docs above.
- [ ] Draft the screen list and a rough sketch (a paper photo is fine) for: citizen home, claim steps, decision result, officer queue. Put it in `docs/screens/`.

### Phase 1 (Sat 09:00 to 15:00): golden path UI
- [x] Role login screen (phone + PIN) with demo personas (built; routing is simple state in `App.tsx`, add a router only if needed).
- [ ] Generate API types from the backend: `npx openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.ts`. Until endpoints exist, use mock data (MSW) shaped like `backend/app/schemas/contracts.py`.
- [x] Citizen claim flow: first version built (`ClaimWizard.tsx`). Improve the visuals.
- [x] Decision result screen: first version built (`CaseResult.tsx`).
- [x] Officer queue: first version built (`OfficerHome.tsx`).
- [ ] Deploy the frontend to Vercel (Stream D) and send the link in the group.

### Phase 2 (Sat 15:00 to 23:00)
- [ ] Offline outbox with Dexie: save each claim step locally; queue actions with an idempotency key; "send now" button; sync on reconnect.
- [ ] Helper Mode: family list, fast switch, clear "now acting for: X" header, only families with consent.
- [ ] Consent screen: who can see my data, toggle fields, withdraw, request correction, "who saw my data". **Backend is ready** (citizen token):
  - `GET /api/v1/me/consents` → `{fields, consents:[{id, grantee_type, grantee_name, fields, status}]}`
  - `PATCH /api/v1/me/consents/{id}` body `{fields:[...]}` · `POST /api/v1/me/consents/{id}/withdraw` · `POST /api/v1/me/consents` to grant again
  - `GET /api/v1/me/access-log` → rows `{ts, action, who, role, field}` (DATA_ACCESS, CONSENT_DENIED, CONSENT_WITHDRAWN...)
  - `POST /api/v1/me/corrections` body `{field: name|date_of_birth|payout_account|family_record, requested_value, reason}`; officer side `GET /api/v1/corrections`, `POST /api/v1/corrections/{id}/approve|reject` body `{note}`
  - Helper family list now returns `consent_active` and hides `cnic` when not shared: show a lock icon and disable "new claim" for those families.
- [ ] Admin rule editor screen + Digital Twin results table. **Backend is ready** (admin token):
  - `GET /api/v1/admin/rules` → versions `{id, version, label, status (live|draft|retired), effective_from, thresholds, rules}`
  - `POST /api/v1/rules/{id}/simulate` → `{checked, changed, cases:[{case, before:{route, reasons, entitlement_end}, after:{...}, changed:[...]}]}` (nothing is saved)
  - `POST /api/v1/rules/{id}/publish` · `POST /api/v1/rules/drafts` body `{label, rules, thresholds, effective_from}` (422 with a clear message if malformed)
  - Demo: simulate v2 shows 2 of 4 past cases change (end date 2034-11-01); publish; Zainab's new claim says "rule v2".
- [ ] Auditor: decision trace view.
- [ ] Urdu audio clips for every prompt and reason code (Stream D), cached by the PWA.

### Phase 3 (Sat 23:00 to Sun 03:30)
- [ ] Scam Shield screen (paste/forward message, verdict, reasons, "is someone on the phone with you?" question).
- [ ] Scam Map + analytics dashboard.
- [ ] Eval page (cost curve chart, false alarms, wrong approvals).
- [ ] Judge console page (buttons listed in docs/05-DEMO-SCRIPT.md).
- [ ] Audit replay screen.

### Phase 4-5 (Sunday)
- [ ] Playwright E2E for the demo script.
- [ ] Test on a real phone with a throttled network.
- [ ] Record the demo video, upload to Google Drive (public link).
- [ ] Slides (optional).

### SafeSwitch endpoints (backend ready)
- `POST /api/v1/cases/{case_id}/payout-change` body `{new_iban}` (citizen or helper with payout consent) → `{id, status (held|flagged), payee_result (match|close_match|no_match), flags, hold_until}`
- `POST /api/v1/payout-changes/{id}/confirm` body `{pin}`: claimant only, re-enters her PIN (helpers get 403)
- `POST /api/v1/payout-changes/{id}/approve|reject` body `{note}` (officer, flagged only) · `GET /api/v1/cases/{case_id}/payout-changes`
- Judge console: `POST /api/v1/admin/payout/apply-due?skip_wait=true` (admin) applies confirmed changes as if the hold passed.

### Scam Shield endpoints (backend ready)
- `POST /api/v1/scam/check` body `{text, sender?, on_call_with_unknown?, area?}` → `{verdict: LIKELY_SCAM|LOOKS_GENUINE|NOT_SURE, confidence, reasons[], reasons_ur[], case_cross_check, report_routes[{name,url}]}`
- `GET /api/v1/scam/map?days=7` (officer/admin/auditor) → `{total_checked, by_verdict, scams_by_type, scams_by_area, scams_by_hour}`
- Mock official sender ID is `PENSION-GOV`. Ask "Is someone on the phone telling you to do this right now?" before checking (big yes/no icons).

## 5. Design facts from research (keep these in the UI)

- Size budget: citizen app shell <= 170 KB total (JS <= 100 KB), each extra screen <= 30 KB, audio clips ~15 KB, photos compressed on the phone to ~200 KB. Check with `npm run build`.
- Never write "fake" or "forged" on screen: document checks say "needs a second look", each with its reason and "what this cannot tell".
- Payout screens show the payee check as **match / close match / no match**.
- Payout confirmation goes to the widow herself, never to the helper's phone.
- Rule v2 in the demo is the **10-year cap for non-spouse heirs (10 Sep 2024)**, not "remarried widows".
- Voice only pre-fills a field; the user always confirms with a tap.
- Full details: [docs/research/survivor-pension.md](docs/research/survivor-pension.md) and the last section of [docs/03-ARCHITECTURE.md](docs/03-ARCHITECTURE.md).

## 6. Rules (important)

- Everything is **mock**: no real names, CNICs, phone numbers or photos anywhere.
- Every page shows the **PROTOTYPE** banner (the component already exists: `src/components/PrototypeBanner.tsx`).
- Never commit `.env` or keys.
- Work on a branch (`feat/c-officer-queue`) and open a pull request into `main`.
- When you finish or get stuck: add a line to [docs/STATUS.md](docs/STATUS.md) and message Aiza.
- Low-literacy first: big touch targets, icons + audio, one decision per screen, works on a cheap phone.
