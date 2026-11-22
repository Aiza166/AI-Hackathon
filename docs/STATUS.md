# STATUS

Updated Sun 22 Nov 2026. Merge freeze 16:00 PKT, submission 17:30 PKT, judging Mon 23 Nov. Detail of every change is in `git log` and the PR list; test results are in [TEST-REPORT.md](TEST-REPORT.md).

## Live

- App: https://confident-growth-production-1cfebeef.up.railway.app
- API and Swagger: https://ai-hackathon-production-31dd3038.up.railway.app/docs
- Railway deploys `main` on every push (about 3-5 minutes). Check `/readyz` after a merge. Services and variable names: [INFRA.md](INFRA.md).

Run locally: `docker compose up -d`, then in `backend/` `alembic upgrade head && python -m app.seed && uvicorn app.main:app --reload`, and in `frontend/` `npm run dev`. Demo logins (PIN 1234, public on purpose): Zainab 00000000001, Rukhsana 00000000002, helper Ayesha 00000000010, officer Kamran 00000000020, admin 00000000030, auditor 00000000040.

## Done

| Area | What | PRs |
|---|---|---|
| Backend core | Login and roles, hash-chained audit log, mock government services with fault injection, name matching, versioned rules (v1 live, v2 draft), decision engine, consent and take-back, SafeSwitch, Digital Twin, idempotent claims | direct commits to `main` (phase 0-2), #4, #5 |
| Citizen screens | Claim wizard with DOB step and photo step, decision result, My data (consent, access log, corrections), Helper Mode (40 families, locked families), SafeSwitch, Scam Shield | #5, #6, #19 |
| Offline | Saved claim steps, outbox with one `Idempotency-Key` per claim, resume after reload | #3 |
| Scam Shield v2 | Share from WhatsApp, screenshot, link and call checks, two-model cascade (Jev, then gpt-5-mini on hard cases) | #20, #33 |
| Documents and voice | Photo checks (OCR, edit indicators, heatmap for the officer), Azure Urdu voice with the phone's voice as fallback | #6 |
| Staff screens | Officer queue with decision trace, payout changes, Scam map; admin Rules, Digital Twin and publish; auditor log and chain check; Evaluation page; Judge console | direct commits, #5, #22 |
| Languages | Urdu, Sindhi, Punjabi text for citizen screens (machine-assisted); Listen labelled as Urdu on Sindhi and Punjabi screens | #28, #38 |
| Security | Hardening against two checklists (148 rows), per-row consent on lists, red-team fixes for decisions, documents and Scam Shield, wrong SafeSwitch PIN gives 403 | #8, #31, #33, #34, #25 |
| Monitoring | Sentry with PII scrubbing, Codecov | #21 |
| Tests | Backend 438 passed, 2 skipped. Playwright 28 tests (13 journeys), 27 passed, 1 opt-in skipped (Run 3). Frontend unit tests 37 passed | #19, #26, #35, #37 |
| Docs | README, 7-minute demo script, judge Q&A cheat-sheet, handoff, security checklist, test report | #29, #30, #32, #35, #36 |

## Left today

- [ ] Live phone check by Kissa on the live site (checklist in TEST-REPORT: Azure voice, Azure document reading, Record and Share on a real phone).
- [ ] One real-user test (10 minutes, anonymous), results in `docs/USER-TEST.md`.
- [ ] Sindhi and Punjabi audio (PR #39 in progress; may not be merged by the freeze).
- [ ] Native Sindhi and Punjabi speakers read `frontend/src/i18n/sd.ts` and `pa.ts`.
- [ ] Demo video, recorded after the 16:00 freeze on the final build, uploaded to Google Drive, link in the README.
- [ ] Rehearsal of the live demo and the Q&A (Aiza and Kissa).
- [ ] Submit by 17:30.

## Known gaps (say these first)

- Ticking a document box counts as having that paper, even with no photo uploaded. The ticks stand in for papers checked at the counter. Real use would count only uploaded and read papers. Fix planned after judging.
- Sindhi and Punjabi text is machine-assisted and has not been read by native speakers. Audio is Urdu (or the new clips from PR #39 if merged).
- Voice input in Urdu is weak (Azure only recognises Indian Urdu). Voice output is good.
- Everything is mock: people, records, bank accounts, government services. Nothing is connected to NADRA, the pension office or Raast.
- Test sets are small and invented (200 claims, 502 name pairs, 80 messages, 20 documents). The numbers describe this prototype only.
- Not built or not tested: a screen to write a new rule draft (v2 is seeded; the API exists), an audit replay screen (API only), a decision trace view in the auditor tab (the trace is in the officer queue), Urdu audio clips shipped with the app (server voice or phone voice is used), a test on a real phone with a throttled network (only emulated Slow 3G in Chromium), a second admin to approve a rule publish, encrypting the offline outbox.
- Dependabot PRs #9-#18 (and the later #23, #24) are left open on purpose until after judging on 23 Nov. They are large version jumps that could break the live site.

## Open questions

- [ ] Organizers' written reply on the prior work (team FYP; see `PRIOR_WORK.md`). Aiza asked on WhatsApp.
- [ ] Jev rate limits (check the console).

## Decisions

| Decision | Why |
|---|---|
| Task: survivor pension claim, with SafeSwitch and Scam Shield | One real decision with a high cost of a wrong approval; all eight challenges arise in the same flow |
| Jev (`jev-1.14.0`, pinned) is a sensor; code and versioned rules decide | Jev has no "abstain" answer; "I am not sure" must be a code route |
| Auto-approve at 0.95 or more, human below 0.70, never auto-reject | Cost ratio 20:1 (wrong approval against delay) |
| No name match without an exact CNIC; document checks are indicators, never "fake" | Research: common name parts carry little evidence; phone-photo forensics is weak |
| Rule v2 = federal 10-year cap for non-spouse heirs (10 Sep 2024) | The only change with a primary source; has a grandfather clause for the Digital Twin |
| Own small JSON rules engine, not GoRules ZEN | Rules are still data; simpler to test and show; fits the size budget |
| Hosting on Railway, no Vercel | One platform for API, database and frontend |
| Prior work (FYP) disclosed, no code reused | Safest option while clearance is pending |
