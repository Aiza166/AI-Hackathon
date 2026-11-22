# Q&A cheat-sheet (Kissa and Aiza)

> Everything in Sahara is a prototype with mock data. Say "mock" or "on our invented test set" whenever a number comes up. Never claim real-world accuracy.

How to use this: say the first sentence of an answer, then stop. Give the rest only if the judge pushes. "Show" says where the proof is in the app, because judges score behaviour, not claims. The numbers come from the app's own Evaluation tab (committed run of 21 Nov, ruleset v1) and the test run of 21-22 Nov (`docs/TEST-REPORT.md`).

## Say the weak spots first

If a judge finds one of these before we say it, it costs more than if we say it ourselves.

- The claim decision is rules plus name matching, not AI. The AI is in Scam Shield, the document checks and the voice.
- Every government record, bank account and person is mock. Nothing is connected to NADRA, the pension office or Raast.
- Our test sets are small and invented: 200 claims, 502 name pairs, 80 messages, 20 documents. The numbers describe this prototype, not the real world.
- Urdu voice input is weak (Azure only recognises Indian Urdu). Voice output is good.
- Sindhi and Punjabi screen text is machine-assisted and not yet reviewed by native speakers. Audio stays Urdu.
- The demo PIN 1234 is public on purpose.
- Known gap, fixed after judging: ticking a document box counts as having that paper, even with no photo uploaded. In the prototype the ticks stand in for papers checked at the counter. Real use would count only uploaded, read papers, which means every claim waits for photos before it can be approved.
- We have not tested with real users yet. One short test with an older woman is planned (task 2, `docs/USER-TEST.md`); update this line once it has happened.

## The product

| Question | Answer |
|---|---|
| Who is this for? | A widow claiming her late husband's family pension who cannot read the forms and has a weak signal; the community helper who serves about 40 families from one phone; the pension officer; and an auditor. |
| What problem, exactly? | Four things go wrong together: she can't read the forms, the records spell her husband's name differently, scammers ask for a "processing fee", and a wrong heir can take the money. A wrong approval pays the wrong person and hurts the real widow twice. |
| Why this task and not a generic relief-payment app? | It is one real decision (approve, ask for proof, or hand to a person) with a high cost of being wrong, and all eight challenges in the brief happen inside that one flow. |
| What did you deliberately not build? | Automatic rejection (only an officer can reject). AI that decides claims (rules and code decide). Generated text for citizens (every line is fixed and reviewed). Any "fake" or "forged" label. Real government data. |
| How do you know it works? | 438 backend tests and 25 browser tests pass, plus the Evaluation tab's measured numbers below. What we cannot claim yet is that real widows find it easy: that needs field testing. |
| What would you do next? | Test with real users and community helpers, get the Sindhi and Punjabi text reviewed, then connect one real registry behind the same API. |

## Decisions and the AI

| Question | Answer | Show |
|---|---|---|
| Why 0.95? | We judge a wrong approval to cost about 20 times a short delay, so auto-approve only when p > 20/21 = 0.952. On our 200 invented claims the cost is flat from 0.50 to 0.99 (110 everywhere), so the threshold is not what keeps people safe there; hard flags and routing do. | Evaluation tab, cost curve |
| Then what does keep people safe? | Hard flags that never auto-approve: payee name doesn't match, duplicate claimant, already drawing a pension. No name match without an exact CNIC. Auto-approval only when her typed date of birth equals the record. | Evaluation, "by category" |
| How many wrong approvals? | 2 of 200 at 0.95 (cost 110, against 130 for never auto-approving). Both are identity theft with her full real credentials, which in the app also needs her phone and PIN, or a helper she gave consent to. | Evaluation, wrong approvals by kind |
| How often does a person have to look? | 69% of our test claims go to a person or ask for proof; 31% auto-approve. Clean claims: 40 of 40 auto-approved. The price of caution is that some genuine widows are asked to confirm their date of birth. | Evaluation |
| Is the claim decision AI? | No. It is versioned rules, fuzzy name matching against the registries, and code thresholds. Jev is used in Scam Shield and document image checks. | `backend/app/decision/` |
| What does Jev do? | Jev (`jev-1.14.0`, pinned) answers small factual yes/no questions, for example "does this message ask for a fee?". Code turns the answers into a verdict. We never ask Jev "is this a scam?" or "should we approve?". Above 0.7 counts as yes, below 0.3 as no, in between as undecided, which means "not sure". | Judge console, live status |
| What if Jev is wrong? | It only answers small questions, and code decides. Undecided answers and any money move with doubt go to a person. | |
| What if Jev is down? | Claims are not affected, because they don't use Jev. Scam Shield falls back to keyword and link rules and never says "looks genuine" (at best "not sure"). Documents still get the registry cross-check, copy-move and ELA, so an edited certificate still goes to an officer. Tested: browser journey J8 with Jev unreachable passed. | Judge console: Jev "Simulate down" |
| What if Azure is down? | Speech: Listen uses the phone's own voice. OCR: Tesseract, or "an officer will read it". gpt-5-mini: Scam Shield runs on Jev plus rules and leaves conflicts unresolved. Every outage switch turns itself off after 15 minutes. | Judge console, outage switches |
| Why two models (Jev and gpt-5-mini)? | Jev is fast and cheap and runs on everything; gpt-5-mini runs only when Jev is unsure. On our 80 messages that took accuracy from 74% (Jev alone) to 84%, with no message called the wrong way. | Evaluation, Scam Shield tiers |

## Security and privacy

| Question | Answer | Show |
|---|---|---|
| Is consent real or just a screen? | It is checked on the server on every read, including list endpoints. When Zainab takes back her helper's access, the helper's very next request gets 403 and the attempt is logged as `CONSENT_DENIED` in Zainab's "who saw my data". | Zainab, My data; then Ayesha |
| Can she take back the department's access too? | Not while she has an open claim with them, because then nobody could process it: the server refuses (409, logged `CONSENT_CHANGE_REFUSED`) and the screen explains why in Urdu and English. She can withdraw the claim first, and then the access ends with it. Helper access can always be taken back. | My data, Pension Department card |
| Who sees what? | Citizen: only her own claims and data, never other people's references or officer names. Helper: only families who gave consent, and only the fields they shared; locked families hide the CNIC; she can start a payout change but never confirm it. Officer: only cases in his department, and only with the department's consent; every approve or reject needs a written reason. Auditor: read-only log, traces and chain check, and auditor reads are logged too. Admin: rules, Digital Twin and the Judge console. All enforced on the server; a citizen token on the officer approve endpoint gets 403. Lists are checked per row too (PR #31): in the case list, the officer queue, corrections and payout changes, a person without an active consent comes back as a locked "Consent withdrawn" row (reference and status only), and each such read is logged as `CONSENT_DENIED` or `DATA_ACCESS`. | Swagger with a citizen token; withdraw consent, then open the helper or officer list |
| What about forged documents? | We never call a document fake or forged. The checks raise indicators for an officer: OCR fields compared with the registry, stamp copy-move, an ELA heatmap, and Jev image questions. Any indicator sends the case to an officer with `DOC_EDIT_RISK`; she hears "your document needs more checking". On our 20 sample documents the rule-based checks caught both edited ones with no false alarms. Limits: phone-photo forensics is weak, we don't verify QR codes (no source says these certificates carry one), and missing EXIF never counts against her. | Upload `death_certificate_aslam_edited.png`; officer heatmap |
| Will Scam Shield scare people with false alarms? | On our 80 invented messages it made no false alarms and missed no scam; 16% came back "not sure" (18% of genuine messages). It never blocks anything; it advises and shows where to report. But 80 invented messages is a small set, and we show the rates on screen instead of claiming 100%. | Evaluation, Scam Shield |
| Can a scammer hide a link or trick Jev? | Hidden links are unpacked before checking ("hxxp", "[.]", "(dot)", spaced or odd dots), WhatsApp and Telegram chat links are flagged, and only the exact official host or a real subdomain counts as official (PR #33). Jev's reply is checked: any answer that is missing, not a number or outside 0 to 1 counts as Jev unavailable, so Scam Shield falls back to its rules instead of trusting it. Links are never opened. | Judge console, Scam Shield sample messages |
| What happens when the app says "I am not sure"? | The claim goes to the officer's queue with reason codes, sorted by priority. Triggers: any red flag, a government service that doesn't answer, or confidence below 0.70. The citizen hears a fixed Urdu reason and that an officer will check (our mock target is 3 days, not an official figure). The app never rejects; only an officer can, with a written reason. | Demo beats 4 and 5 |
| What stops a scammer changing her payout account? | SafeSwitch: every change is held 48 hours, or 4 working days when flagged. A mock bank name check says match, close match or no match. Someone else's account is flagged for an officer, and even her own PIN does not release it. A helper can start a change but cannot confirm it. | Demo beat 3 |
| Can the audit log be edited? | Rows are append-only (a database trigger blocks UPDATE, DELETE and TRUNCATE) and each row is SHA-256 hash-chained to the one before, so `/audit/verify` detects any change. Known limit: the app's database user owns the table; production would use a separate role that cannot drop the trigger. | Auditor, verify: "Chain intact" |
| What if someone steals her phone or guesses her PIN? | 5 wrong PINs lock that account for 15 minutes, at login and at the SafeSwitch PIN step. PINs are bcrypt-hashed. Refresh tokens rotate, reuse revokes the whole session, and sign-out revokes it. | |
| Do you leak personal data in logs? | CNICs and IBANs are masked in the audit log and app logs, and error reports to Sentry drop request bodies and mask CNICs, IBANs, phone numbers and PINs. | `docs/INFRA.md`, monitoring |
| What security checks did you run? | Two public checklists (GitHub Well-Architected and Invicti, 148 rows), an independent security review, plus pip-audit, npm audit, Bandit and gitleaks. Strict browser security headers (CSP) are on; our 360 px test found nothing blocked. | `docs/SECURITY-CHECKLIST.md` |
| Many judges on one venue Wi-Fi? | Login is limited to 60 per minute per IP, and wrong PINs lock only that account, so one judge can't lock out the room. | |

## Real or simulated

| Part | Real or simulated |
|---|---|
| NADRA-like identity, family record, death registry, pension office | Simulated (mock APIs, seeded mock data) |
| Raast-like payments and the bank name check | Simulated |
| Jev | Real API calls, pinned `jev-1.14.0` |
| gpt-5-mini second sensor, Azure OCR, Azure Urdu voice | Real when keys are set; safe fallbacks without them |
| Rules, consent, audit log, login and roles | Real, written in this project |
| Documents and messages used in the demo | Mock specimens and invented messages |

Full table: `README.md`, "Real vs simulated".

## Prior work (our FYP)

Short answer: "All code was written during the event. A team member's final year project researched scam SMS detection; we used that understanding, not its code, models or data."

If they push: the FYP ("Call and Link Scam Detection", FAST-NUCES Karachi) studied scam messages in Pakistan, including with Jev. No code, trained models, data files or assets from it are in this repository, and the git history starts inside the hackathon window (first commit 21 Nov, 00:20 PKT). Every number we show was measured during the event on this project's own test sets. The pension claim, consent, rules, audit and payout protection were never part of the FYP. Aiza asked the organisers for written clearance (`PRIOR_WORK.md`).

## The numbers and their limits

| Area | What we measured (invented test sets) | Limit to say |
|---|---|---|
| Claims (200 cases, 130 should be approved) | At 0.95: 2 wrong approvals (identity theft with full credentials), cost 110 vs 130 for never auto-approving, 31% auto-approved, 69% to a person or asked for proof, clean claims 40/40 | Invented cases; the cost ratio 20:1 is our judgement, not a measured figure |
| Name matching (502 pairs) | False matches: 0 of 252 different people, and 0 of 40 impostors who know the exact CNIC. 42% of same-person pairs are not auto-matched; they are asked for proof or sent to a person, never rejected | We trade convenience for safety on purpose |
| Scam Shield (80 messages: 46 scam, 34 genuine; English 35, Roman Urdu 26, Urdu 19) | Full cascade: 84% right, no false alarms, no missed scams, 16% "not sure", median 451 ms, about 3 US cents for all 80. Jev alone: 74%. Rules alone: 13% (mostly "not sure") | Small, invented set; real scams change fast |
| Documents (20 samples, 2 edited) | Rule-based checks: 20/20. Jev alone: 40% (missed both edited ones). Full cascade: 80% with 20% undecided, no false alarms, no misses, about 5 s each | Very small set; edits made by us |
| Tests | 438 backend tests and 25 browser tests (12 journeys) pass on localhost; 360 px phone width checked; Jev-down journey passes | Localhost and mock services only |

## Rule v1 to v2 (if they ask about the law)

Use the "Judge Q&A risks (rule v1 to v2)" table in `docs/05-DEMO-SCRIPT.md`. Short version: v2 is the federal 10-year cap for heirs after the spouse (O.M. 10-09-2024); we model federal civil-service family pension only; when a child's 10-year clock starts is our labelled assumption.

## Security fixes from the red-team review (as of Sun 22 Nov, morning)

All three PRs are merged and live. Say only what is listed here.

- PR #31: consent is checked per row on every list. A row whose owner took back consent shows "Consent withdrawn" instead of her details, and the refusal is logged. A helper can't cancel a payout change without consent. Money never moves on a closed or rejected claim.
- PR #33: Scam Shield unpacks disguised links (`hxxp`, `[.]`, `(dot)`, odd dots) before checking them. A broken or out-of-range Jev answer counts as Jev being down, so the keyword rules run and the answer is never "looks genuine".
- PR #34:
  - Sending the same claim many times at once gives one claim (database lock plus a unique index); the rest get "you already have an open claim".
  - A case with an officer can never drop back to auto-approved when a paper is uploaded or a rule is published.
  - A flagged paper stays flagged until an officer clears it with a written reason (the "Clear this flag" button, audited).
  - The duplicate check also catches a claim filed once without the husband's CNIC and again with it.
  - Typed corrections are only accepted for fields she was asked to confirm.
  - A paper missing its fields shows as "unverified", not "low risk".
- Not done, deferred to after judging: ticked document boxes without uploads (see "Say the weak spots first"), the second admin for publishing a rule, PIN and session changes, and encrypting the offline outbox.
