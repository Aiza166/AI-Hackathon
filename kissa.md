# Kissa: start here

> Owner: **Kissa** (GitHub `Kissa-Zehra`), Streams C (frontend PWA) and D (demo & quality).

> Your personal task list. Aiza (and Claude) keep this updated. Tick boxes as you finish and push.
> Last updated: Sat 21 Nov ~04:00. **Phase 1 is built** (backend + a first version of your screens). Read section 0 first.

## Start here (Sat 21 Nov evening handoff)

Read **[docs/HANDOFF.md](docs/HANDOFF.md)** first: the whole project in plain words, what is done, your task list, and the merge rules.

Your tasks now (details in HANDOFF section 5):
- [ ] 1. Full test of the merged app (Playwright + your phone); results in `docs/TEST-REPORT.md`
  - Local part done Sat evening (TEST-REPORT "Run 2"): pytest 438 passed / 2 skipped, Playwright 25 passed + Jev-down passed, new 360 px journey (J12), one bug fixed (demo toggle 44 -> 48 px). **Still to do:** live-site phone check (checklist in TEST-REPORT), Azure-key parts, rerun after the security-fixes branch merges.
- [ ] 2. One real-user test (10 min, anonymous) -> `docs/USER-TEST.md`
- [ ] 3. Sindhi + Punjabi text for citizen screens (labelled machine-assisted)
- [x] 4. Demo script trimmed to one story
  - Done Sun (`docs/c-demo-one-story`): `docs/05-DEMO-SCRIPT.md` now opens with one 7-minute story (Zainab claims, scam SMS caught, SafeSwitch holds a payout change to someone else's account, Rukhsana's competing claim goes to Kamran, auditor verifies the chain) with exact clicks, one line to say per beat, and what judges see. Every beat was run on the local stack first. Digital Twin, Evaluation, Judge console and the full persona list moved under "If judges ask". Rehearse it once with Aiza.
- [ ] 5. Q&A cheat-sheet (`docs/QA-CHEATSHEET.md`), rehearse Sunday

**Dependabot PRs #9-#18: leave them open. Do not merge or close.** You may squash-merge your own PRs once CI is green; ask Aiza for backend logic, security or migration changes.

Note: older update notes below say "Sun" for some Saturday work; they were all written on Sat 21 Nov.

## 0. What changed overnight (read first)

**Update Sun (Aiza + Claude): Evaluation page and Judge console.** Officer, admin and auditor have a new **Evaluation** tab (lazy-loaded, not in the citizen bundle): cost curve with 0.95 and the "never auto-approve" line (arrow keys step through thresholds), name-matching rates, Scam Shield and document tier tables (deterministic / Jev only / full cascade with model ids), and "Show as table" under every chart. Admin has a **Judge console** tab: break each mock service (ok / timeout / error / slow), simulate Jev, gpt-5-mini, Azure OCR or Azure speech being down (auto-off after 15 min), live status, persona list, Scam Shield samples with Copy buttons, sample document downloads, reset demo, and the last 20 audit events every 10 s. Admin tabs now scroll sideways on a phone instead of pushing the page wider. Playwright: `frontend/e2e/tests/j11-eval-judge.spec.ts`.
**Update Sun (Aiza + Claude): Scam Shield v2.** `src/pages/ScamShield.tsx` now has three modes (Message or link / Screenshot / Phone call), a Paste button, screenshot upload, voice-note upload and a Record button (only where the phone supports it). The result view moved to `src/components/ScamVerdict.tsx` and lists the links we checked (never opened) and what was read or heard. Installed app: "Share" from WhatsApp/SMS opens Scam Shield prefilled (`src/lib/share.ts`, `public/share-target-sw.js`). Please check at 360 px: the 3-mode choice, the file pickers, the Record button, Urdu line breaks; record clips for `prompt_scam_intro` (new text). Browser test of share/screenshot/recording is planned for the end.
**Update Sun ~06:00 (Aiza + Claude): E2E bugs fixed** (details in `docs/TEST-REPORT.md`, "Fix status"). What changes for you:
- Admin -> Rules -> Run Digital Twin now has an "On publish" column; publishing v2 caps the Haider heirs (Bilal sees "paid until 2034-11-01"), Rakha stays v1. Reset the demo to repeat it.
- My data: the Pension Department card has no "Take back" while a claim is open; it explains why (Urdu + English) and offers "Withdraw my claim" for a claim still being decided (a paid pension keeps the department's access). Please check the Urdu wording and line breaks.
- Home shows a "No signal" note and still opens the saved claim after an offline reload.
- "Fill demo data" no longer fills the DOB (use "Fill demo DOB" on the DOB step).
- Helper Mode: Mehrunnisa is a locked family in the seed.
- `.btn-sm` is now 48 px; scam report "source" links are 48 px tap targets.
- E2E suite lives in `frontend/e2e` (own package). Run against a local stack with `VITE_PROXY_TARGET=http://localhost:8010 npx vite --port 5180 --strictPort` (no override file needed). Frontend unit tests: `npm run test:unit`.

**Update Sat ~23:30 (Aiza + Claude): Scam Shield, SafeSwitch, Scam Map and officer payout screens are built** (first versions, yours to polish). What is new:
- Claim wizard has a **date of birth step** (step 2). Auto-approval now needs her DOB to match the record; blank DOB = "Please confirm your date of birth", never a rejection. "Fill demo DOB" appears for Zainab.
- Citizen and helper home: two new tiles, **"Is this message a scam?"** (`src/pages/ScamShield.tsx`) and **"Change payout account"** (`src/pages/SafeSwitch.tsx`). Both are lazy-loaded so the first screen stays small.
- Officer: tabs **Review queue / Payout changes / Scam map** (`OfficerPayouts.tsx`, `ScamMap.tsx`). Admin has a Scam map tab too.
- Backend: mock Raast title fetch (masked title like "ZA**** BI**", joint/single, wallet/account), cancel a payout change, officer list of flagged changes, real report routes (1799, PTA, Sunwai, BISP when relevant).

**Please test on your phone (live app after deploy):**
1. Zainab: new claim, fill demo DOB + demo data, send: should be auto-approved. Try again with the DOB empty on a fresh reset: should ask to confirm the DOB.
2. Zainab: "Is this message a scam?", Fill demo scam SMS, say Yes to "someone on the phone", Check: red verdict, reasons, Listen, and the "Report this scam" card (tap 1799 should open the dialer).
3. Zainab: "Change payout account", Demo: Joint account: close match, joint account reason, ~5 day countdown; Cancel this change. Then Demo: Own wallet: match, enter PIN 1234, "Confirmed".
4. Ayesha (helper), pick Zainab, Change payout account: she sees the change but no PIN box.
5. Kamran (officer): Payout changes tab (flag one first with Zainab using "Demo: Someone else's"), reject with a note; Scam map tab shows counts.
6. Check Urdu line breaks and 48 px targets at 360 px width; record Urdu clips for `prompt_dob`, `prompt_scam_intro`, `prompt_safeswitch`, `scam_likely_scam`, `scam_not_sure`, `scam_looks_genuine`, `reason_confirm_dob`, `reason_dob_mismatch`.

**Update Sat ~05:30:** the UI was redesigned (design system in `src/index.css`, pictograms in `src/lib/icons.tsx`, shared pieces in `src/components/ui.tsx`). Already built: My data (consent) screen, helper lock states, admin Rules + Digital Twin, officer and auditor layouts, Demo mode toggle on login. **Still yours:** Scam Shield screen + Scam Map, SafeSwitch (change payout account + confirm with PIN) screens, offline outbox (Dexie), Urdu audio clips, phone-width check, Playwright E2E. Backend endpoints for all of these are listed below.

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
- [x] Do the setup above; run the frontend; push one small commit (e.g., your name in this file) so we know access works. (Docker setup done, tests pass.)
- [x] Read the 3 docs above.
- [x] Draft the screen list and a rough sketch (a paper photo is fine) for: citizen home, claim steps, decision result, officer queue. Put it in `docs/screens/`. (Text sketches in [docs/screens/README.md](docs/screens/README.md).)

### Phase 1 (Sat 09:00 to 15:00): golden path UI
- [x] Role login screen (phone + PIN) with demo personas (built; routing is simple state in `App.tsx`, add a router only if needed).
- [ ] Generate API types from the backend: `npx openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.ts`. Until endpoints exist, use mock data (MSW) shaped like `backend/app/schemas/contracts.py`.
- [x] Citizen claim flow: first version built (`ClaimWizard.tsx`). Improve the visuals.
- [x] Decision result screen: first version built (`CaseResult.tsx`).
- [x] Officer queue: first version built (`OfficerHome.tsx`).
- [ ] Deploy the frontend to Vercel (Stream D) and send the link in the group.

### Phase 2 (Sat 15:00 to 23:00)
- [x] Offline outbox with Dexie: save each claim step locally; queue actions with an idempotency key; "send now" button; sync on reconnect. (Merged as PR #3; Dexie is lazy-loaded in its own chunk.) **Changed in review (Aiza + Claude):** a 401 keeps the claim and shows "Sign in again to send"; each claim keeps one UUID as `Idempotency-Key` on every attempt (the server now honours it); save + send run inside one lock (Web Locks across tabs); the draft stays until the claim is confirmed sent; refused claims (4xx) come back as "Open and fix"; a 409 shows the existing reference; sign-out deletes your drafts and unsent claims (in-page confirm); drafts expire after 7 days; Helper Mode shows only the selected family's claims; capped backoff after server errors; Dexie loads only when something is stored. Not yet checked in a real browser after these changes: please run the offline demo once (go offline, Send, reconnect).
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
  - Update Sun: `speak()` now falls back to the server's Azure Urdu voice (`POST /api/v1/speech/tts`, cached in the Cache API) before the phone voice, so missing clips still sound natural online. Pre-recorded clips are still worth it for offline.
- [ ] Click through the new photo step (wizard after "Send claim", and "Send photos of papers" on the claim page) at phone width; officer case panel now shows document indicators + ELA heatmap. Sample images: `backend/sample_docs/`.

### Phase 3 (Sat 23:00 to Sun 03:30)
- [x] Scam Shield screen (paste/forward message, verdict, reasons, "is someone on the phone with you?" question). First version built; polish it.
- [x] Scam Map (officer + admin tab, counts by district/type/hour). Analytics dashboard still open.
- [x] Eval page (cost curve chart, false alarms, wrong approvals). Built Sun by Aiza + Claude: staff tab "Evaluation" (officer, admin, auditor). Please check it at tablet width.
- [x] Judge console page (buttons listed in docs/05-DEMO-SCRIPT.md). Built Sun: admin tab "Judge console". Please rehearse the demo with it.
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
