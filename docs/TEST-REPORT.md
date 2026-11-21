# Sahara E2E test report

## Run 2: full test of the merged app (Sat 21 Nov 2026, evening, Kissa)

- **Build tested:** `main` at `12423bd` (after #19-#22 and #25), plus this branch's one CSS fix.
- **Where:** localhost only, on Kissa's laptop. Backend :8010 on its own database `sahara_e2e`, Vite dev :5180, production build via `vite preview` :5181. The live Railway site was not used.
- **Keys:** real Jev key (`jev-1.14.0`). **No Azure keys** (speech, document reading, gpt-5-mini) and no Sentry DSN, so those parts ran on their fallbacks; see "Not covered" below.
- **How:** Playwright 1.65.1 + Chromium. Phone 390x844 (touch) as before, plus a new journey at **360x780**; staff screens at 1280x900.

### Result

| Suite | Result |
|---|---|
| Backend `pytest` (440 tests) | **438 passed, 2 skipped, 0 failed**. The 2 skips are voice-note tests that need `ffmpeg`, which is not installed on this laptop |
| Playwright, final full run (26 tests, 5.4 min) | **25 passed, 0 failed, 1 skipped** (Jev unreachable: needs its own backend) |
| Jev unreachable, run separately (backend with `TYPESAFE_BASE_URL=http://127.0.0.1:9`) | **passed**: `/readyz` said `jev_reachable: false`; Scam Shield still answered safely and never "looks genuine"; claims still worked |
| New: J12 every citizen + helper screen at 360 px | **passed after one fix** (21 screens: 0 sideways scroll, all Urdu RTL, all tap targets >= 48 px, **0 Content-Security-Policy blocks**) |
| Console errors | One per run, expected: `POST /speech/tts` -> 503 `TTS_NOT_CONFIGURED` (no Azure speech key here); the app then uses the phone's voice |

All earlier bugs B1-B11 stay fixed: borderline Scam Shield message = `NOT_SURE` (B1); publishing v2 re-decides the pending Haider heirs to v2, Rakha stays v1 (B2); "Fill demo data" leaves a blank DOB blank (B3); offline reload resumes at "3 / 7" (B4).

Security behaviour checked on the way (all held): helper cannot confirm a payout with a PIN (403); citizen cannot call the officer approve endpoint (403) or read decision traces (403); officer cannot open the Judge console (403); consent take-back blocks the helper's next request (403, `CONSENT_DENIED` in her access log); auditor chain verify "intact"; replaying an `Idempotency-Key` returns the same case (one claim, one `201`).

### Measured

| What | Value |
|---|---|
| Slow 3G cold load (production build) | first render 3.8 s, FCP 3.3 s, 96 KB on the wire (budget 170 KB) |
| Offline reload (service worker) | app shell loads, saved claim resumes at step 3 / 7 |
| Offline send then reconnect | 1 case on the server, one `201` |
| Digital Twin v2 | 4 checked, 2 change (SP-0001, SP-0002 -> 2034-11-01) |
| Helper Mode | 40 families; locked ones hide the CNIC |
| axe (WCAG 2.1 A/AA) at 390 px | 0 serious or critical |

### Bug found and fixed in this PR

| ID | Severity | Bug | Fix |
|---|---|---|---|
| B12 | LOW | The login screen's "Demo accounts (mock)" / "Hide demo accounts" toggle was 44 px tall, under the 48 px rule (J9 recorded it but did not fail; J12 fails on it) | `.demo-toggle` `min-height: 48px` (`frontend/src/index.css`). J9 and J12 pass |

### Not covered on this laptop (check on the live site or with keys)

- **Azure speech:** Listen was tested with the phone's voice only (server TTS 503). Check that the live site's Listen uses the Azure voice.
- **Azure document reading:** without OCR the edited death certificate goes to an officer as `OCR_UNAVAILABLE` + `NEEDS_OFFICER` (safe: in review, never approved) instead of `DOC_EDIT_RISK`. Check `DOC_EDIT_RISK` and the heatmap on the live site.
- **gpt-5-mini second sensor:** Scam Shield ran on Jev + rules only.
- **Voice notes and real recording:** `ffmpeg` is missing here (2 backend tests skipped); Record and Share need a real phone.
- **Security-fixes branch:** not merged when this ran. Its screen changes (redacted rows after consent take-back, "scheduled" rule status, second-admin approval, forgery-flag clear button, new warning codes) were **not** tested; rerun J1, J7, J11 and J12 after it merges.

### What to tap on the phone (live site, once Aiza says OK)

Use a real Android phone, Chrome, mobile data or a weak hotspot.

1. Open the live app: the PROTOTYPE banner shows, the page does not scroll sideways.
2. Demo accounts (mock) -> Zainab. Start a new claim, fill the DOB with "Fill demo DOB", then "Fill demo data", send. Expect **approved**.
3. On the result, tap **Listen**: it should be a natural Urdu voice (Azure), not the robot phone voice.
4. Photo step: take a real photo of any printed page (no real ID), and upload `death_certificate_aslam_edited.png` from the Judge console samples: the case goes to an officer with "needs a second look", never "fake".
5. Scam Shield: Fill demo scam SMS -> red verdict, Listen, tap **1799** (dialer opens; do not call). Try **Screenshot** with a screenshot of the demo SMS, and **Record** a few seconds.
6. Change payout account: Demo: Own wallet -> PIN 1234 -> confirmed.
7. Airplane mode mid-claim, Send, then turn signal back on: claim sends once, strip disappears.
8. Watch for anything that does not load (blank picture, silent Listen); if a laptop is handy, check the browser console for "Refused to ...".

---

## Run 1 (Sat 21 Nov 2026, earlier)

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

### Fix status

Fixed in `fix/e2e-findings` (PR #19), except B1 and B7, which the Scam Shield v2 branch owns.

| ID | Fixed in | How (test) |
|---|---|---|
| B1 | Scam Shield v2 branch (not here) | |
| B2 | #19 | Seed: the Haider heirs' claims SP-0001/SP-0002 are pending (`in_review`, the heirs asked an officer to check shares); the Rakha claims are officer-approved. Publishing a rule version re-decides only pending cases whose entitlement starts on or after its effective date (audited `CASE_REDECIDED`, listed in `RULES_PUBLISHED`), keeps them with the officer, and never touches decided cases. Digital Twin shows "On publish: Re-decided / Keeps its version" (`will_redecide`). Tests: `test_rule_versions.py` (5 new, 1 updated), `j07` |
| B3 | #19 | "Fill demo data" never sets the DOB. Test: `j02` (now a hard expectation) |
| B4 | #19 | Last `/me` cached in sessionStorage (scoped to the user id, minimal fields, cleared on sign-out); home shows a "No signal, you can continue your saved claim" note (Urdu + English) and the saved draft opens offline. Tests: `frontend/unit/meCache.test.ts` (7, `npm run test:unit`), `j10` |
| B5 | #19 | Server refuses to withdraw (or hide fields of) the Pension Department's consent while the claimant has an open claim with it: 409, audited `CONSENT_CHANGE_REFUSED`. New `POST /cases/{id}/withdraw` (claimant only, only while the claim is still being decided; final status `withdrawn`, audited `CASE_WITHDRAWN`, open payout change cancelled, later uploads never re-open it); then the department's access can be taken back. A paid (approved) claim keeps the department's access while it is paid. Filing a claim while the department's access is taken back is refused. My data explains this in Urdu + English and offers "Withdraw my claim" when allowed. Helper access stays freely revocable. Tests: `test_consent.py` (9 new), `test_documents_api.py` (updated), `j01` |
| B6 | #19 | 05-DEMO-SCRIPT Q&A, 03-ARCHITECTURE (principle 6, diagram, `service_health`) and 02-COMPLIANCE now say Jev is used only for Scam Shield and document checks; claims use registries + rules + code thresholds; what Jev-down does in each place |
| B7 | Scam Shield v2 branch (not here) | |
| B8 | #19 | FRC uses `DOC_ICONS.frc` (family icon) |
| B9 | #19 | `.btn-sm` is 48 px; report-card source links are 48x48 px tap targets (`index.css`) |
| B10 | #19 (partly) | Seed has one locked helper family (Mehrunnisa). Test: `test_seed_has_exactly_one_locked_helper_family`, `j03`. Judge console page: not built |
| B11 | #19 | `vite.config.ts` reads `VITE_PROXY_TARGET` (dev and preview), so the README snippet works without `vite.e2e.config.ts` |
| Login limit (observation) | #19 | PIN lockout stays per account (5 wrong / 15 min); per-IP login limit raised from 10 to 60 per minute for a shared venue IP. Tests: `test_pin_lockout_is_per_account_not_per_venue`, `test_login_per_ip_limit_allows_a_room_of_judges_but_is_still_limited` |

Browser rerun after the fixes (localhost, own DB, Vite with `VITE_PROXY_TARGET` and no override file): `j07` 2/2 and `j02` 4/4 passed in 2.4 min. The full suite was not rerun yet (planned for final testing).

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
