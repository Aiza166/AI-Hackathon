# 05. Demo script: one story

> Everything in the app is mock: people, records, bank accounts and government services. The PROTOTYPE banner stays on screen the whole time.

The live demo is one story of about 7 minutes. A widow claims her late husband's pension, a scammer goes after the money, the app protects her, and a person decides the case the app was not sure about. Judges score behaviour, so every beat is something they watch happen on the phone. Digital Twin, the Evaluation page and the Judge console come out only if judges ask (see "If judges ask" below).

Every beat below was run on a local stack on Sun 22 Nov with these exact clicks and gave these results.

## People in the story (all mock, PIN 1234)

| Persona | Phone | Part in the story |
|---|---|---|
| Zainab Bibi | 00000000001 | The widow. Her husband "Muhammad Aslam" is "Mohd. Aslam" on the death certificate and "Muhammed Aslam" at the pension office |
| Rukhsana | 00000000002 | Claims the same pension. She is not in the family record |
| Kamran | 00000000020 | Pension officer |
| Auditor | 00000000040 | Checks the audit log at the end |
| Admin | 00000000030 | Resets the demo before you start |

The full persona list is under "If judges ask".

## Before you start (5 minutes)

1. Sign in as Admin, open the Judge console tab, tap Reset demo data, then Yes. This restores the seed data, ends any faults and signs everyone out.
2. Use one phone, or a laptop browser at phone width (about 390 px), for every persona. To switch: Sign out, then "Demo accounts (mock)" on the login screen.
3. Turn the volume up and tap Listen on the login screen once.
4. Optional: set the browser to Slow 3G for the opening (Chrome DevTools, Network).
5. Keep the backup video open in another tab.

## The story (about 7 minutes)

### 0:00-0:30 Opening

Show the login screen.

Say: "Zainab can't read forms, her signal is weak, and scammers go after widows like her. Sahara helps her claim her husband's pension and keeps the money safe."

Judges see the PROTOTYPE banner, Urdu text with a Listen button, and (once PR #28 is merged) the language choice: Urdu, Sindhi, Punjabi.

### 0:30-2:00 Zainab claims

Click: Demo accounts (mock), Zainab, "Start a new pension claim", Widow, Next, "Fill demo DOB (mock)", Next, "Fill demo data (mock)", Next until the review screen, Send claim, then Continue on the photo step.

Say: "One question per screen, with a picture and Urdu, and she can tap Listen on every step. Each step is saved on the phone, so a dropped signal loses nothing."

Judges see: approved, with the reason in Urdu and English. Tap Listen. Her husband's name matched across three spellings because his CNIC matched; a name alone never matches.

Optional, 30 seconds: turn on airplane mode just before Send claim. The claim waits on the phone with "saved on this phone, waiting to send". Turn signal back on and it is sent once.

### 2:00-3:00 A scam SMS arrives

Click: Back to home, "Is this message a scam?", "Fill demo scam SMS (mock)", answer Yes to "Is someone on the phone telling you to do this right now?", then "Check this message".

Say: "Someone calls her: your pension is released, pay a fee at this link. She pastes the message."

Judges see a red "likely scam" verdict (0.98 on our run) with reasons in Urdu and English: it asks for a fee, the link imitates an official address, it did not come from the official sender, it pressures her, and someone is on the phone. Below that, the "Report this scam" card with NCCIA 1799 and PTA.

### 3:00-4:00 The caller wants the pension moved

Click: Back, "Change payout account", "Demo: Someone else's", "Check account and request change". Optional: enter PIN 1234.

Say: "The caller tells her to move her pension to a new account. SafeSwitch checks whose name is on that account."

Judges see: no match. The change is flagged and held for about 4 working days for an officer. Even when she enters her own PIN it stays held. No money moves.

### 4:00-4:45 A second woman claims the same pension

Click: Sign out, Demo accounts (mock), Rukhsana, "Start a new pension claim", Widow, Next (leave the date of birth empty), "Fill demo data (mock)", Next until the review screen, Send claim, Continue.

Say: "Another woman says she is the widow and asks for the same pension, paid to the same account."

Judges see: the app does not reject her. It says an officer will look at her claim. Zainab's approved claim is paused as well, because two people now claim one pension.

### 4:45-6:15 The officer decides

Click: Sign out, Kamran, Review queue. Open Rukhsana's claim: read the reason codes and the decision trace, type a reason, Reject. Open Zainab's claim: type a reason, Approve. Then the Payout changes tab: open the flagged change, type a note, Reject.

Say: "The app never rejects anyone on its own. When it is not sure, a person decides and writes down why."

Judges see the codes the app gave: ACCOUNT_REUSED, ACCOUNT_NOT_OWNED and NOT_IN_FAMILY_RECORD on Rukhsana's claim, DUPLICATE_CLAIM on Zainab's. Each decision needs a written reason, and the flagged account change is rejected.

### 6:15-7:00 Close

Click: Sign out, Auditor, verify the chain.

Say: "Every action, by a person, the AI or the system, goes into a log that can't be quietly changed." Then the honest limits: everything is mock; the claim decision is rules plus name matching; the AI is in Scam Shield, the document checks and the voice; our test sets are small and invented, and we say so on screen.

Judges see "Chain intact" with the number of events checked (1,005 on our run).

## If something goes wrong on stage

| What happens | Do this |
|---|---|
| "You already have an open claim" | The demo was not reset. Admin, Judge console, Reset demo data |
| Listen is silent | Check the volume. Without signal or without the Azure voice, the phone's own voice reads it |
| A demo account is locked (5 wrong PINs) | Use another persona, or reset the demo |
| Venue internet fails | Switch to the local stack on the laptop, or play the backup video |

## If judges ask

### Things judges can try

| They want to see | Show |
|---|---|
| The rules change (Digital Twin) | **Publish rule v2: federal 10-year cap for heirs after the spouse (O.M. 10-09-2024).** v1 = O.M. No. 1(13)-Reg.6/83 as updated 24-06-2024 (widow for life till remarriage, then children/daughters, no time cap). v2 = O.M. F.No. 9(3)R-6/2024-264 dated 10-09-2024 (+ clarifications 10-10-2024, 22-01-2025). Admin, Rules, v2 (draft), **Run Digital Twin**: 4 past cases checked, 2 change (SP-0001, SP-0002: "Paid until" No limit -> 2034-11-01), and the "On publish" column says SP-0001/SP-0002 "Re-decided" (pending, entitled after 10-09-2024) and SP-0003/SP-0004 "Keeps its version" (decided). Nothing is saved. **Publish v2**, Yes: v1 retired, v2 live; SP-0001/SP-0002 get a new decision under v2 (audited `CASE_REDECIDED`, from v1 to v2; `RULES_PUBLISHED` lists them), stay in the officer's queue, and Bilal (`00000000005`) sees "paid until 2034-11-01" on his claim. The Rakha cases (approved, 2019) still show "decided under rule v1". Zainab (widow) files a new claim: decided under v2, unaffected by the heir cap. Reset the demo to run it again. Sources: [v1](https://www.finance.gov.pk/circulars/circular_24062024.pdf), [v2](https://www.finance.gov.pk/circulars/circular_10092024_1.pdf), [10-10-2024](https://www.finance.gov.pk/circulars/circular_10102024_1.pdf), [22-01-2025](https://www.finance.gov.pk/circulars/circular_22012025.pdf) |
| Why 0.95, and how good it is | Evaluation tab (officer, admin or auditor), labelled "synthetic test set": the cost curve with 0.95 and the never-auto-approve line (arrow keys step through thresholds; "Show as table" under every chart), wrong approvals by kind, human-review rate, name-matching rates, and per-tier tables for Scam Shield and documents (deterministic only, Jev only, full cascade: accuracy, FPR, FNR, NOT SURE, median and p95 latency, cost per check, model ids). The cost curve is flat (110 from 0.50 to 0.99), so 0.95 comes from the 20:1 cost ratio and the safety comes from hard flags and routing: 2 wrong approvals of 200 (both identity theft with full credentials), cost 110 vs 130 for never auto-approving, 69% sent to a person, clean claims 40/40 auto-approved |
| A helper on a shared phone | Ayesha (`00000000010`): 40 families, Mehrunnisa shows locked (no consent). Pick Zainab: "Now acting for: Zainab Bibi". She can start a payout change but sees no PIN box; the PIN confirm is refused on the server (403) |
| Consent take-back | Zainab, My data: take back Ayesha's access. Ayesha's next request returns 403, logged as `CONSENT_DENIED`. The Pension Department card has no "Take back" while she has an open claim (server refuses with 409, audited `CONSENT_CHANGE_REFUSED`); for a claim still being decided it offers "Withdraw my claim" |
| An edited death certificate | Download `death_certificate_aslam_edited.png` from the Judge console, upload it from Zainab's claim ("Send photos of papers"): the case goes to an officer (`DOC_EDIT_RISK`, with a heatmap for the officer); the citizen hears a polite "needs checking", never "fake" |
| The look-alike name | A claim for the other "Muhammad Aslam" (different CNIC and date of birth): not matched, `NAME_MISMATCH`, no money moves |
| A blank date of birth | File Zainab's claim with the DOB empty ("Fill demo data" never fills it): "Please confirm your date of birth. It is printed on your CNIC." Never a rejection. A wrong DOB gives `DOB_MISMATCH` |
| A borderline message | Ambiguous message: "not sure", never silently "looks genuine" |
| Offline | File a claim offline, reconnect: sent exactly once. Reload with no signal: "No signal, you can continue your saved claim" and the saved draft opens |
| A citizen calling an officer endpoint | In Swagger with a citizen token: 403 on approve, attempt logged |

### Judge console (admin only, every action audited)

Sign in as **Admin** (`00000000030`, PIN 1234) and open the **Judge console** tab (yellow "PROTOTYPE / DEMO CONTROLS" banner). The server checks every call (platform admin only; citizens, helpers, officers and auditors get 403, logged `ACCESS_DENIED`) and writes every change to the audit log.

| Panel | Click | What they should see |
|---|---|---|
| Break a mock government service | NADRA identity / FRC / Death registry / Pension office: **timeout** or **error** | The next claim goes to an officer with `SERVICE_UNAVAILABLE`, no guess, no crash. **slow** waits 1.5 s and still answers. Set **ok** to restore |
| | Raast title fetch: **timeout** | New claim UNSURE; a payout change is flagged `PAYEE_CHECK_TIMEOUT`, held 4 business days |
| Simulate an AI provider outage | Jev: **Simulate down** | Live status shows "simulated outage"; Scam Shield still answers from keyword + link rules and never says "looks genuine"; a document upload still gets copy-move + registry checks (Jev recorded "unavailable"); a clean claim can still auto-approve (Jev is not used for claims) |
| | Second sensor (gpt-5-mini): **Simulate down** | Cascade = Jev + deterministic checks; conflicts stay "unresolved" |
| | Azure OCR: **Simulate down** | Screenshot / document reading falls back to Tesseract (or "an officer will read it") |
| | Azure speech: **Simulate down** | Listen buttons use the phone's own voice; voice-note check asks her to type |
| | Every outage switch | Turns itself off after 15 minutes and on demo reset; audited `AI_OUTAGE_SIMULATED` |
| Live status | **Refresh** | DB, Jev reachable + `jev-1.14.0`, which AI providers are configured (yes/no only, never a key), last evaluation run, audit chain "Intact" |
| Recent activity | (auto, every 10 s) | The judge's own actions appear within 10 s: `MOCK_FAULT_SET identity: timeout`, `DECISION_MADE UNSURE: SERVICE_UNAVAILABLE`, `ACCESS_DENIED` rows highlighted |
| Demo shortcuts | **Rules: Digital Twin and publish v2**; **Reset demo data** (in-page confirm) | Opens the rules tab; reset restores the seed, ends faults and outages, signs everyone out |
| Scam Shield: messages to paste | **Copy** message + sender, then sign in as Rafiq or Zainab, "Is this message a scam?" | Fee scam, look-alike link and spoofed 8171 call = LIKELY_SCAM; "call this number" = NOT_SURE; genuine notice = LOOKS_GENUINE |
| Sample documents | Download `death_certificate_aslam_edited.png`, upload it from Zainab's claim ("Send photos of papers") | Case goes to an officer (`DOC_EDIT_RISK`), citizen hears a polite "needs checking" |

### All seed personas (all mock)

| Persona | Role | What is special about their data |
|---|---|---|
| Zainab Bibi | Citizen (widow) | Husband "Muhammad Aslam" is "Mohd. Aslam" on the death certificate and "Muhammed Aslam" in the pension office |
| Rukhsana | Citizen (competing claimant) | Claims the same pension; **not** in the family record, so a red flag |
| Saima | Citizen (lawful second widow) | In the family record: a lawful co-sharer, shown with her share, not a fraud flag |
| Bilal, Hina Haider | Citizens (new heir case) | Children of Ghulam Haider; their widowed mother Shamim died 2024-11-01, so their entitlement starts after 10-09-2024. Their claims SP-0001/SP-0002 are **pending** (decided by the AI under v1, then the heirs asked an officer to check the share split; status `in_review`). Publishing v2 re-decides them: capped at 10 years (end 2034-11-01), still with the officer |
| Sajida, Naveed Rakha | Citizens (old heir case) | Children of Allah Rakha; their widowed mother died 2019. Claims SP-0003/SP-0004 were **approved by an officer** under v1: decided cases are never re-decided, and 2019 is before the cap anyway, so they stay pinned to v1 with no end date |
| Muhammad Aslam (2) | Mock registry only | Different man, same name, different CNIC and DOB: must never be matched |
| Ayesha | Community helper | 40 seeded families on one phone; one (Mehrunnisa) has taken back Ayesha's access, so it shows locked |
| Rafiq | Citizen (shopkeeper) | Inbox full of fake "pension released, pay fee" messages |
| Kamran | Pension officer | Review queue |
| Admin | Admin | Rule editor, judge console |
| Auditor | Auditor | Read-only traces and replay |

## Logins at the venue

Judges share one venue IP. Login is limited to **60 per minute per IP** (still rate limited), and wrong PINs lock **only that account**: 5 wrong PINs = 15 minutes locked (`LOGIN_LOCKED` in the audit log); other accounts on the same IP keep working. If a judge locks a demo account, use another persona or reset the demo.

## Backup plan

- Pre-recorded full demo video (same as the submission video), on the laptop and on Drive.
- Local stack (`docker compose up`) with seeded data on the laptop, in case venue internet fails.
- Phone hotspot as a second network.
- Seed reset button in case a judge leaves the data in a strange state.

## Q&A prep: likely judge questions

The full cheat-sheet, with the security answers and the measured numbers, is `docs/QA-CHEATSHEET.md`. The short version:

| Question | Our answer (short) |
|---|---|
| Why 0.95? | Cost ratio 20:1 between wrong approval and delay gives p > 0.952. Our own sweep is honest about it: on the 200-case test set the cost is flat from 0.50 to 0.99, so the threshold is not what keeps people safe there. Hard flags (payee, duplicate, already drawing), "no match without exact CNIC" and "auto-approve only when her typed DOB equals the record" do that. The eval shows 2 wrong approvals at 0.95 (cost 110 vs 130 for never auto-approving): both hold the widow's real CNIC and know her exact name and DOB, which in the app needs her phone/PIN or a helper with her consent. The price: 6 more genuine claimants are asked to confirm their DOB. |
| What if Jev is wrong? | Jev only answers small factual questions. Rules and code decide. Undecided Jev answers (0.3-0.7) and any money move with doubt go to a human. |
| What if Jev is down? | Jev is used only for Scam Shield and document image checks; claim decisions come from the registries, the rules and code thresholds. With Jev down, Scam Shield uses a keyword fallback that never says "looks genuine" (NOT_SURE at best), and documents still get the registry cross-check, stamp copy-move and ELA, so an edited certificate still goes to an officer (Jev's answer is recorded as "unavailable"). A clean claim can still be auto-approved, because nothing Jev answers is needed for it. What stops money is a registry or bank-check outage: then the claim routes UNSURE with SERVICE_UNAVAILABLE and she hears that it is saved. |
| How do you stop a wrong name match? | Names alone never match, and nothing auto-matches without an exact CNIC. DOB plus husband/father name can only lead to "ask for proof" or a human. We show the false-match rate. |
| Do you verify the certificate's QR code? | No. QR verification is not built and not confirmed: no primary source says these certificates carry one. Missing EXIF never counts against the claimant. |
| Is "within 3 days" official? | No, it is our mock target. No official processing time exists. |
| Is consent real or just UI? | Enforced in the API on every read; withdrawal blocks the next request; the blocked attempt is in the audit log. |
| Can the audit log be edited? | The app's DB role cannot UPDATE or DELETE it, and each row is hash-chained; `/audit/verify` detects tampering. |
| What about false alarms on real people? | We never auto-reject. Scam and document checks raise risk for a human; we publish false-alarm rates instead of claiming 100%. |
| What is real and what is simulated? | See the README table: government and payment services are mock; Jev, rules, consent, audit, auth are real. |
| Did you build this before? | All code was written during the event. Our FYP researched scam SMS detection; see PRIOR_WORK.md. |
| How would this scale or go real? | Mock services sit behind clean APIs and can be swapped for real ones; rules are data; tenants are separate departments. |

## Judge Q&A risks (rule v1 to v2)

From `research_notes/survivor-pension/verify_E_rule_v2.md` (parent folder, outside the repo).

| Risk question | Our answer (short) |
|---|---|
| When does a child's 10-year clock start? | The O.M. says the cap runs "after the death or ineligibility of the spouse", and the 22-01-2025 O.M. speaks of the "un-expired portion of 10 years". It does not say explicitly for children, so starting the clock at the spouse's death or ineligibility is our **assumption**, labelled in the ruleset. |
| Does v2 cover the armed forces? | Unconfirmed. The O.M. is copied to MAG and Dawn reported armed forces from 2025-26, but no MoD/GHQ instrument was found. We model federal civil-service family pension only. Special Family Pension (Shuhada) is a different rule (25 years, 50%). |
| EOBI widows keep their pension after remarriage. | EOBI is a separate private-sector scheme: EOBI Act s.22B gives the surviving spouse a "life pension" with no remarriage condition. We model government family pension only. |
| A remarried spouse kept a pension in KP. | Peshawar High Court 2025 (Said Qamar) protected a remarried widower's pension sanctioned in 2017 only because the 2021 KP rule was not retrospective. It does not let remarried widows keep family pension. |
| What about Punjab? | Punjab restricted family pension to the spouse (notifications 02-12-2024 and 20-08-2025). LHC 2026 LHC 8584 (hearing 28-10-2026) declared them without lawful authority to the extent they exclude eligible family members; appeal status unknown. That is why our demo uses the federal rule. |
| Which dates are exact? | v2 O.M. dated 10-09-2024, "with immediate effect" (the "1 July" in Dawn was the ECC plan). Supreme Court divorced-daughter judgment (C.P. 616-K/2025) dated 10-07-2025, reported 30-07-2025. |
