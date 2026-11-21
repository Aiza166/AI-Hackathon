# Sahara E2E test report

- **Build tested:** `main` at `5f521e6` (docs: infrastructure note), Sat 21 Nov 2026.
- **Where:** localhost only. Backend on :8010 against its own database `sahara_e2e` (seeded, reset before each journey), Vite dev on :5180, production build via `vite preview` on :5181. The live Railway site was never used.
- **How:** Playwright 1.65 + Chromium, phone 390x844 (touch) for citizen/helper screens, 1280x900 for staff screens. Specs: `frontend/e2e/tests/` (rerun steps in `frontend/e2e/README.md`). Real Jev and Azure keys from `backend/.env` were used (never printed).
- **Run:** 21 tests in 11.5 min: 16 passed, 4 failed (each failure is one of bugs B1-B4 below, the same in every run, so none are flaky), 1 skipped (Jev-down needs a specially started backend; run separately: passed).

## Summary

| # | Journey | Result | Notes |
|---|---|---|---|
| 1 | Zainab: UI login, wizard incl. DOB + photo step, AUTO_APPROVE, Listen, My data, consent take-back | **PASS** | CNIC photo read with fields to confirm, death certificate risk `low`; reasons in Urdu (RTL) + English; Listen sent `POST /speech/tts` -> 200 (Azure voice); after take-back the helper gets 403 and `CONSENT_DENIED` is in her access log |
| 2 | Blank DOB -> ASK_PROOF; wrong DOB -> DOB_MISMATCH; edited certificate -> UNSURE + DOC_EDIT_RISK + heatmap | **PASS with 1 bug** | All three routes correct, never rejected, no "fake/forged" text. Bug B3: "Fill demo data" quietly fills a DOB the user left blank |
| 3 | Helper mode: family picker, locked families, acting-for banner, cannot confirm SafeSwitch PIN | **PASS** | No family is locked in the seed (all 40 share access), so the test locks Zainab by withdrawing consent first. Helper sees no PIN box; `POST /payout-changes/{id}/confirm` as helper -> 403 |
| 4 | Scam Shield: fee scam, genuine message, sender 8171 | **PASS (main) / FAIL (borderline)** | Fee scam -> LIKELY_SCAM, report card with 1799 (`tel:`), PTA, BISP line only when BISP is mentioned; "from 8171" still LIKELY_SCAM. Bug B1: ambiguous messages from unknown numbers come back LOOKS_GENUINE |
| 5 | SafeSwitch: joint ...0012 flagged; wallet ...0013 confirmed with PIN; cancel; officer approve/reject | **PASS** | Joint -> `flagged`, `close_match`, cancel -> `cancelled`; wallet shows `ZA**** BI**`, wrong PIN refused, right PIN -> confirmed; officer rejects "someone else's" and approves joint; approval leaves `confirmed=false` (PIN still needed) |
| 6 | Offline outbox | **PASS with 1 bug** | Offline send -> "1 claim is saved on this phone, waiting to send"; sign-out shows the in-page confirm; back online -> exactly 1 case on the server and exactly one `201`; replaying the same `Idempotency-Key` returns the same case. Bug B4 (production build): after a reload with no signal she cannot reopen her saved draft |
| 7 | Officer queue + decision + audit; auditor chain verify; admin Digital Twin + publish v2 | **PARTIAL** | Officer approve writes `CASE_APPROVED`; auditor filter + "Chain intact: N events checked"; auditor approve -> 403. Digital Twin: 2 of 4 change, end 2034-11-01. Publish works and Zainab's next claim is decided under v2. Bug B2: publishing does not touch the Haider case (still v1, no end date) and no new heir claim can be filed (409, heirs already hold open seeded claims) |
| 8 | Fault injection | **PASS** | Raast `timeout` -> claim UNSURE `SERVICE_UNAVAILABLE` with a polite citizen message; payout change `flagged` + `PAYEE_CHECK_TIMEOUT`, PIN does not apply it. Identity `error` -> UNSURE `SERVICE_UNAVAILABLE`. Jev unreachable (backend restarted with a dead `TYPESAFE_BASE_URL`): scam check -> NOT_SURE (never genuine), edited certificate still -> UNSURE `DOC_EDIT_RISK`; a clean claim still auto-approves (see B6) |
| 9 | Accessibility / basics | **PASS with LOW items** | PROTOTYPE banner on every screen checked; every `lang="ur"` element is RTL; no horizontal scroll at 390 px on 9 screens; axe (WCAG 2.1 A/AA): 0 serious/critical; keyboard focus visible on the login form. Small targets: all `btn-sm` are 44 px tall, "source" links are 20 px (B9) |
| 10 | Performance | **PASS** | Citizen shell ~94 KB gzip (JS 87 KB, CSS 7 KB) vs budget 170 / 100 KB. Slow 3G (400 ms RTT, 400 kbps), cold, cache off: first render 3.4 s, FCP 3.3 s, 94 KB on the wire |

Console errors: none recorded in any journey (React/Vite noise and expected 4xx excluded).

## Bugs

| ID | Severity | Bug |
|---|---|---|
| B1 | **HIGH** | Scam Shield labels ambiguous / pretext messages from unknown numbers "looks genuine", even while listing "It did not come from the official sender" |
| B2 | **HIGH** | Publishing rule v2 does not re-decide existing cases, and the demo has no way to file a new heir case, so "publish -> Haider case capped" cannot be shown |
| B3 | MEDIUM | "Fill demo data (mock)" silently fills Zainab's DOB when she left it blank, so the "leave the DOB blank" judge test auto-approves |
| B4 | MEDIUM | With no signal after a reload / app restart, the citizen cannot reopen her saved claim (button disabled) |
| B5 | MEDIUM | Citizen can take back the Pension Department's access with one confirm, which locks officers out of her own pending claim; the confirm text does not say so |
| B6 | MEDIUM (docs) | Q&A says "Jev down -> money never moves, UNSURE"; in code claim decisions never call Jev, so a clean claim auto-approves with Jev down |
| B7 | LOW | Scam case cross-check Urdu line is hard-coded "no payment pending" whatever the English line says |
| B8 | LOW | Family certificate (FRC) on the photo step shows a "?" icon |
| B9 | LOW | Tap targets under 48 px: all `btn-sm` (Sign out, Back, demo buttons) are 44 px; "source" links in the report card are ~38x20 px |
| B10 | LOW | No locked family in the seed, and no judge-console page yet (faults, reset, competing claimant are API/Swagger only) |
| B11 | LOW (dev) | `vite.config.ts` hard-codes the `/api` proxy to `:8000`, so a second local stack needs a config override |

### B1 (HIGH) Scam Shield says "looks genuine" for unknown-sender pretext messages

Repro (Zainab, Scam Shield, or `POST /api/v1/scam/check`, Jev up):

| Message | Sender | Verdict | Reasons shown |
|---|---|---|---|
| "Salam, aap ke pension case ke baare mein office se call aayegi. Apna CNIC tayyar rakhein." | 03001234567 | LOOKS_GENUINE (0.14) | "It did not come from the official sender." |
| "Pension office: please visit the nearest branch with your original CNIC to complete verification." | 03211234567 | LOOKS_GENUINE (0.13) | same |
| "Your pension verification is pending. Reply YES to continue." | 8171 | LOOKS_GENUINE (0.06) | none |
| "Aap ka pension case update hua hai. Details ke liye is number par WhatsApp karein 03451234567." | (none) | LOOKS_GENUINE (0.20) | "Your claim shows no payment waiting for you." |

Expected (demo script, "Send borderline message"): NOT_SURE, never silently safe. A green "looks genuine" next to a red flag reason is contradictory and is the kind of thing judges will try.
Suspected cause: `backend/app/services/scam.py:139`: `LOOKS_GENUINE` only requires `score <= 0.3`, no money doubt and no fallback; it ignores whether any warning key (`unofficial_sender`, `no_payment_pending`, claims to be government) was added. `unofficial_sender` only multiplies risk by 0.9 (line ~121). Suggested rule: LOOKS_GENUINE only when the sender is official (or no warning key fired); otherwise NOT_SURE. (The Scam Shield v2 branch may already change this; rerun `j04` there.)

### B2 (HIGH) Rule v2 publish does not change the Haider case; no new heir case possible

Repro: admin -> Rules -> v2 (draft) -> Run Digital Twin (shows SP-0001, SP-0002 -> 2034-11-01) -> Publish v2 -> Yes. Then as Bilal (`00000000005`) `GET /api/v1/cases` -> SP-0001 still `rule_version 1`, explanation `entitlement_end: null`. Filing a new claim as Bilal or Hina -> 409 "You already have an open claim for this pension (SP-0001/SP-0002)".
Expected (05-DEMO-SCRIPT): "Publish; the Haider case is capped at 10 years under v2; the Rakha case still shows decided under rule v1".
Suspected cause: `backend/app/services/rules.py:102` `publish()` only flips statuses and writes `RULES_PUBLISHED`; nothing re-decides open cases the Twin flagged. Either re-run the decision for open cases whose Twin result changed (new decision row with rule v2, audited), or seed the Haider heirs without open claims so a fresh claim can be filed live.

### B3 (MEDIUM) "Fill demo data" fills a blank DOB

Repro: Zainab -> Start a new pension claim -> Next -> leave DOB empty -> Next -> "Fill demo data (mock)" -> Next x4 -> review shows "Your date of birth 1962-06-01". Sending gives AUTO_APPROVE instead of ASK_PROOF.
Suspected cause: `frontend/src/pages/ClaimWizard.tsx:200` `if (claimant.cnic === DEMO_CLAIMANT.cnic && !dob) setDob(DEMO_CLAIMANT.dob)`. A judge following the script ("leave the DOB blank") with the quick demo button gets the opposite result. Remove that line (the DOB step has its own "Fill demo DOB" button).

### B4 (MEDIUM) Saved draft cannot be reopened offline after a reload

Repro (production build with service worker, `vite preview`): Zainab -> new claim -> fill DOB -> step 3 ("Saved on this phone") -> go offline -> reload. The shell loads from the service worker (good), but home shows "No connection" and "Start a new pension claim" is disabled, so her saved claim is unreachable until signal returns. Screenshot `docs/test-screens/j10-offline-reload-no-resume.png`.
Suspected cause: `frontend/src/pages/CitizenHome.tsx:77` builds the claimant only from `GET /api/v1/me` (`me?.person`), and line 140 disables the button when it is null. Cache the last `me` (or the claimant cnic/name) in session storage / IndexedDB and allow opening the draft offline. The demo's "connection drops mid-way, progress saved, resumes" works only if the page is not reloaded.

### B5 (MEDIUM) Taking back the department's access blocks her own claim without warning

Repro: Zainab -> My data -> "Pension Department (mock)" card -> Take back all access -> Yes. The department consent is withdrawn; officer reads of her data now need consent (`backend/app/core/consent.py:34`), so a pending claim cannot be reviewed: verified, officer `GET /cases/{id}` -> 403 and `POST /cases/{id}/approve` -> 403. The confirm says only "Pension Department (mock) will not be able to see any of your data after this." (`frontend/src/pages/MyData.tsx:~170`). Found because the first version of the J1 test tapped the first card, which is the department. Suggest: warn "your claim cannot be processed while this is off" (Urdu + English), or keep the department card read-only while a claim is open.

### B6 (MEDIUM, docs) Jev-down answer in the Q&A does not match the code

`docs/05-DEMO-SCRIPT.md` Q&A: "What if Jev is down? Money never moves; the case routes UNSURE with SERVICE_UNAVAILABLE." In code, claim facts never call Jev (`backend/app/services/cases.py:158` `model_id=None # Jev is not used for claim facts`), so with Jev unreachable a clean claim still AUTO_APPROVEs (tested). Scam checks fall back safely (NOT_SURE) and document checks still route edited papers to an officer. Fix the Q&A wording (Jev powers Scam Shield and document checks; claim decisions are rules only).

### B7 (LOW) Cross-check Urdu line is fixed text

`frontend/src/pages/ScamShield.tsx:179` always shows "آپ کے دعوے میں کوئی ادائیگی باقی نہیں۔" next to whatever `case_cross_check` says in English. Today the backend only sends the "no payment waiting" line, so it matches, but any new cross-check text would be mistranslated. Send `case_cross_check_ur` from the backend.

### B8 (LOW) FRC icon is a question mark on the photo step

`frontend/src/components/DocumentCapture.tsx:18` uses icon name `'frc'`, which is not in the icon set (`lib/icons.tsx` falls back to `question`). Use `DOC_ICONS.frc` (`'family'`). Visible in `docs/test-screens/j1-03-photo-step.png`.

### B9 (LOW) Tap targets

Measured at 390 px (all visible buttons/links/inputs): only `.btn-sm` (44 px tall: Sign out, Back on Scam Shield/My data, "Fill demo …" buttons, "Hide demo accounts") and the six "source" links on the scam report card (about 38x20 px) are below 48 px. Big citizen buttons, choices, tiles and Listen are fine.

### B10 (LOW) Demo gaps

All 40 helper families share access in the seed, so "locked families" only appear after a withdrawal. The judge console page does not exist yet: faults, reset and the competing claimant are API-only (`POST /api/v1/admin/faults`, `/admin/seed/reset`).

## Other observations (not bugs)

- Duplicate claims: a second claim for the same pension returns 409 with the existing reference; the demo needs a reset between golden-path runs.
- Helper's claim list title says "Claims filed from this phone" but it lists every consented family's claims (Zainab's own claim appears for Ayesha).
- Wrong DOB routes ASK_PROOF (`DOB_MISMATCH`), so it does not appear in the officer queue; the officer test uses a competing-claimant case (Rukhsana -> UNSURE `ACCOUNT_NOT_OWNED, NOT_IN_FAMILY_RECORD`).
- The PWA precaches 481 KiB (all chunks, including staff screens) on a citizen's first visit.
- Login is limited to 10/minute per IP; the tests log in through the API and wait out 429s. In the live demo many judges on one venue IP could hit this.

## Screenshots

`docs/test-screens/` (viewport-size PNGs, under 2 MB total): `j1-*` golden path, `j2-*` DOB and documents (incl. officer heatmap), `j3-*` helper, `j4-*` Scam Shield, `j5-*` SafeSwitch, `j6-*` offline, `j7-*` staff, `j8-*` fault, `j10-*` offline reload.
