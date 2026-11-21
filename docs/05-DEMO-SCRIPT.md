# 05. Demo Script, Judge Console and Q&A

> Judges score behaviour, not claims. The demo is built so judges can **break it themselves** and then watch the audit replay.

## Seed personas (all mock)

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

## The 8-minute live demo

| Time | Segment | What happens on screen | Challenge |
|---|---|---|---|
| 0:00-0:45 | Hook | Zainab's story in one sentence. Phone on throttled "Slow 3G". PROTOTYPE banner visible. | 7 |
| 0:45-2:15 | Golden path | Ayesha switches to Zainab (Helper Mode). Claim by voice and icons; connection drops mid-way, progress saved, resumes. Name variants matched safely. Auto-approved with Urdu audio reason. Payout to her verified account. | 3, 5, 7 |
| 2:15-3:00 | Cost of being wrong | Eval page: cost curve is flat (110 from 0.50 to 0.99), so 0.95 comes from the 20:1 cost ratio and the safety comes from hard flags and routing. Show the measured numbers: 2 wrong approvals of 200 (both identity theft with full credentials, which needs an account takeover), cost 110 vs 130 for never auto-approving, 69% sent to a person, clean claims 40/40 auto-approved, payee/duplicate/already-drawing never auto-approved. Auto-approval needs her typed DOB to equal the record; a blank DOB is asked again, never rejected. Say plainly what is still open. | 1 |
| 3:00-6:00 | **Judges break it** (judge console) | See the console list below. Each action shows its effect live. | 2, 3, 4, 6, 8 |
| 6:00-7:00 | Auditor replay | Auditor steps through the events just triggered: actor, role, rule version, model ID, probabilities, blocked attempts. `/audit/verify` shows the chain is intact. | 5 |
| 7:00-8:00 | Honest limits | What is real vs simulated, measured false-alarm rate, what we would validate next. | all |

## Judge console (admin-only, every action audited)

| Button | Expected behaviour |
|---|---|
| **Add competing claimant** | Rukhsana claims the same pension: Zainab's case pauses, route UNSURE, officer sees both side by side |
| **Try the look-alike name** | Claim using the other "Muhammad Aslam": not matched, NAME_MISMATCH, no money moves |
| **Publish rule v2: federal 10-year cap for heirs after the spouse (O.M. 10-09-2024)** | v1 = O.M. No. 1(13)-Reg.6/83 as updated 24-06-2024 (widow for life till remarriage, then children/daughters, no time cap). v2 = O.M. F.No. 9(3)R-6/2024-264 dated 10-09-2024 (+ clarifications 10-10-2024, 22-01-2025). Admin -> Rules -> v2 (draft) -> **Run Digital Twin**: 4 past cases checked, 2 change (SP-0001, SP-0002: "Paid until" No limit -> 2034-11-01), and the "On publish" column says SP-0001/SP-0002 "Re-decided" (pending, entitled after 10-09-2024) and SP-0003/SP-0004 "Keeps its version" (decided). Nothing is saved. **Publish v2** -> Yes: v1 retired, v2 live; SP-0001/SP-0002 get a new decision under v2 (audited `CASE_REDECIDED`, from v1 to v2; `RULES_PUBLISHED` lists them), stay in the officer's queue, and Bilal (`00000000005`) sees "paid until 2034-11-01" on his claim. The Rakha cases (approved, 2019) still show "decided under rule v1". Zainab (widow) files a new claim: decided under v2, unaffected by the heir cap. Reset the demo to run it again. Sources: [v1](https://www.finance.gov.pk/circulars/circular_24062024.pdf), [v2](https://www.finance.gov.pk/circulars/circular_10092024_1.pdf), [10-10-2024](https://www.finance.gov.pk/circulars/circular_10102024_1.pdf), [22-01-2025](https://www.finance.gov.pk/circulars/circular_22012025.pdf) |
| **Withdraw consent** | Zainab withdraws Ayesha's access: Ayesha's next request returns 403, logged as CONSENT_DENIED. Helper access is always freely revocable |
| **Take back the department's access with a claim open** | Zainab -> My data -> Pension Department card: no "Take back" button while she has an open claim. The server refuses the take-back (409, audited `CONSENT_CHANGE_REFUSED`) and also refuses hiding single fields; helper access stays freely revocable. If the claim is still being decided (e.g. blank DOB -> "One more paper is needed"), the card explains in Urdu + English and offers **Withdraw my claim**: status `withdrawn` (audited `CASE_WITHDRAWN`, final: officers, uploads and payout changes can no longer act on it; an open payout change is cancelled), then the department's access ends with it. If the claim is already approved and being paid (golden path), the card says the department keeps this access while the pension is paid (no button). With the department's access taken back, a new claim is refused until she shares again |
| **Upload edited certificate** | Edit-risk indicators raised, case to officer, citizen hears a polite "needs checking" message |
| **Send scam SMS** | Fee/OTP message from an unofficial sender: LIKELY_SCAM, reasons shown, case cross-check says no payment pending. The same message "from 8171" is still LIKELY_SCAM: content outweighs sender ID because 8171 has been spoofed |
| **Scam Shield screen (citizen or helper)** | Tile "Is this message a scam?": paste the message (or "Fill demo scam SMS"), sender, "is someone on the phone with you?" yes/no, district. LIKELY_SCAM shows reasons in Urdu + English with Listen, the case cross-check line, and a "Report this scam" card: NCCIA 1799 (tel:), NCCIA portal, PTA complaint portal + 0800-55055, forward to 9000 (per PTA, 2023), call your bank, SBP Sunwai; BISP 0800-26477 only when the message mentions BISP. Officer and admin see it on the **Scam map** tab |
| **Send borderline message** | Ambiguous message: NOT_SURE, never silently labelled safe |
| **Change payout account** | Zainab's tile "Change payout account" (demo buttons fill mock IBANs). Own wallet (...0013): mock Raast title fetch shows "ZA**** BI**", match, held 48 hours with a countdown, confirmed with her own PIN. Joint account (...0012): close match + "joint account, proof needed", flagged, 4 business days. Someone else's account (...0008): no match, flagged. A helper can start a change but sees no PIN box. Cancel any time. Officer tab **Payout changes** approves or rejects flagged ones with a note (approval still needs her PIN and the hold) |
| **Break the bank check (Raast timeout)** | `POST /api/v1/admin/faults {"service": "raast", "mode": "timeout"}`: a new claim goes UNSURE with SERVICE_UNAVAILABLE; a payout change is flagged PAYEE_CHECK_TIMEOUT, held 4 business days, her PIN alone does not release it. Set mode `ok` to restore |
| **Leave the DOB blank** | File Zainab's claim with the DOB step empty (the later "Fill demo data" button never fills the DOB): ASK_PROOF, "Please confirm your date of birth. It is printed on your CNIC." Never a rejection. A wrong DOB gives DOB_MISMATCH |
| **Break the identity service** | Mock NADRA returns errors: case routes UNSURE with SERVICE_UNAVAILABLE, no crash, no guess |
| **Go offline** | File a claim offline, reconnect: syncs exactly once. Reload the app with no signal: home says "No signal, you can continue your saved claim" and the saved draft opens (last profile cached in this tab only) |
| **Citizen calls officer API** | In Swagger with a citizen token: 403 on approve endpoint, attempt logged |
| **Reset demo** | Seed data restored in one click |

## Logins at the venue

Judges share one venue IP. Login is limited to **60 per minute per IP** (still rate limited), and wrong PINs lock **only that account**: 5 wrong PINs = 15 minutes locked (`LOGIN_LOCKED` in the audit log); other accounts on the same IP keep working. If a judge locks a demo account, use another persona or reset the demo.

## Backup plan

- Pre-recorded full demo video (same as the submission video), on the laptop and on Drive.
- Local stack (`docker compose up`) with seeded data on the laptop, in case venue internet fails.
- Phone hotspot as a second network.
- Seed reset button in case a judge leaves the data in a strange state.

## Q&A prep: likely judge questions

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
