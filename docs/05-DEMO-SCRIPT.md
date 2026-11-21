# 05. Demo Script, Judge Console and Q&A

> Judges score behaviour, not claims. The demo is built so judges can **break it themselves** and then watch the audit replay.

## Seed personas (all mock)

| Persona | Role | What is special about their data |
|---|---|---|
| Zainab Bibi | Citizen (widow) | Husband "Muhammad Aslam" is "Mohd. Aslam" on the death certificate and "Muhammed Aslam" in the pension office |
| Rukhsana | Citizen (competing claimant) | Claims the same pension; **not** in the family record, so a red flag |
| Saima | Citizen (lawful second widow) | In the family record: a lawful co-sharer, shown with her share, not a fraud flag |
| Bilal, Hina Haider | Citizens (new heir case) | Children of Ghulam Haider; their widowed mother Shamim died 2024-11-01, so their entitlement starts after 10-09-2024: capped at 10 years under rule v2 (end 2034-11-01) |
| Sajida, Naveed Rakha | Citizens (old heir case) | Children of Allah Rakha; their widowed mother died 2019: decided under rule v1, exempt from the cap, stays pinned to v1 |
| Muhammad Aslam (2) | Mock registry only | Different man, same name, different CNIC and DOB: must never be matched |
| Ayesha | Community helper | 40 seeded families on one phone |
| Rafiq | Citizen (shopkeeper) | Inbox full of fake "pension released, pay fee" messages |
| Kamran | Pension officer | Review queue |
| Admin | Admin | Rule editor, judge console |
| Auditor | Auditor | Read-only traces and replay |

## The 8-minute live demo

| Time | Segment | What happens on screen | Challenge |
|---|---|---|---|
| 0:00-0:45 | Hook | Zainab's story in one sentence. Phone on throttled "Slow 3G". PROTOTYPE banner visible. | 7 |
| 0:45-2:15 | Golden path | Ayesha switches to Zainab (Helper Mode). Claim by voice and icons; connection drops mid-way, progress saved, resumes. Name variants matched safely. Auto-approved with Urdu audio reason. Payout to her verified account. | 3, 5, 7 |
| 2:15-3:00 | Cost of being wrong | Eval page: cost curve, why 0.95, wrong approvals = 0, UNSURE rate. | 1 |
| 3:00-6:00 | **Judges break it** (judge console) | See the console list below. Each action shows its effect live. | 2, 3, 4, 6, 8 |
| 6:00-7:00 | Auditor replay | Auditor steps through the events just triggered: actor, role, rule version, model ID, probabilities, blocked attempts. `/audit/verify` shows the chain is intact. | 5 |
| 7:00-8:00 | Honest limits | What is real vs simulated, measured false-alarm rate, what we would validate next. | all |

## Judge console (admin-only, every action audited)

| Button | Expected behaviour |
|---|---|
| **Add competing claimant** | Rukhsana claims the same pension: Zainab's case pauses, route UNSURE, officer sees both side by side |
| **Try the look-alike name** | Claim using the other "Muhammad Aslam": not matched, NAME_MISMATCH, no money moves |
| **Publish rule v2: federal 10-year cap for heirs after the spouse (O.M. 10-09-2024)** | v1 = O.M. No. 1(13)-Reg.6/83 as updated 24-06-2024 (widow for life till remarriage, then children/daughters, no time cap). v2 = O.M. F.No. 9(3)R-6/2024-264 dated 10-09-2024 (+ clarifications 10-10-2024, 22-01-2025). Digital Twin first shows which seeded past cases would change: only the Haider heirs (entitled after 10-09-2024). Publish; the Haider case is capped at 10 years under v2; the Rakha case (2019) still shows "decided under rule v1"; Zainab (widow) is unaffected. Sources: [v1](https://www.finance.gov.pk/circulars/circular_24062024.pdf), [v2](https://www.finance.gov.pk/circulars/circular_10092024_1.pdf), [10-10-2024](https://www.finance.gov.pk/circulars/circular_10102024_1.pdf), [22-01-2025](https://www.finance.gov.pk/circulars/circular_22012025.pdf) |
| **Withdraw consent** | Zainab withdraws Ayesha's access: Ayesha's next request returns 403, logged as CONSENT_DENIED |
| **Upload edited certificate** | Edit-risk indicators raised, case to officer, citizen hears a polite "needs checking" message |
| **Send scam SMS** | Fee/OTP message from an unofficial sender: LIKELY_SCAM, reasons shown, case cross-check says no payment pending. The same message "from 8171" is still LIKELY_SCAM: content outweighs sender ID because 8171 has been spoofed |
| **Send borderline message** | Ambiguous message: NOT_SURE, never silently labelled safe |
| **Change payout account** | Held 48 hours, needs Zainab's PIN; account used by other claims is flagged and the hold extends up to 4 business days |
| **Break the identity service** | Mock NADRA returns errors: case routes UNSURE with SERVICE_UNAVAILABLE, no crash, no guess |
| **Go offline** | File a claim offline, reconnect: syncs exactly once |
| **Citizen calls officer API** | In Swagger with a citizen token: 403 on approve endpoint, attempt logged |
| **Reset demo** | Seed data restored in one click |

## Backup plan

- Pre-recorded full demo video (same as the submission video), on the laptop and on Drive.
- Local stack (`docker compose up`) with seeded data on the laptop, in case venue internet fails.
- Phone hotspot as a second network.
- Seed reset button in case a judge leaves the data in a strange state.

## Q&A prep: likely judge questions

| Question | Our answer (short) |
|---|---|
| Why 0.95? | Cost ratio 20:1 between wrong approval and delay gives p > 0.952; the eval page sweep shows it is near the minimum-cost point on our test set. |
| What if Jev is wrong? | Jev only answers small factual questions. Rules and code decide. Undecided Jev answers (0.3-0.7) and any money move with doubt go to a human. |
| What if Jev is down? | Money never moves; the case routes UNSURE with SERVICE_UNAVAILABLE and the citizen hears that the claim is saved. |
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
