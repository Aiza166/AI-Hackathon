# 05. Demo Script, Judge Console and Q&A

> Judges score behaviour, not claims. The demo is built so judges can **break it themselves** and then watch the audit replay.

## Seed personas (all mock)

| Persona | Role | What is special about their data |
|---|---|---|
| Zainab Bibi | Citizen (widow) | Husband "Muhammad Aslam" is "Mohd. Aslam" on the death certificate and "Muhammed Aslam" in the pension office |
| Rukhsana | Citizen (competing claimant) | Claims the same pension; not in the family record |
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
| **Publish rule v2** | Remarried widows stay eligible; next case decided under v2; old cases still show v1; Digital Twin shows how many past cases would change |
| **Withdraw consent** | Zainab withdraws Ayesha's access: Ayesha's next request returns 403, logged as CONSENT_DENIED |
| **Upload edited certificate** | Edit-risk indicators raised, case to officer, citizen hears a polite "needs checking" message |
| **Send scam SMS** | Fee/OTP message from an unofficial sender: LIKELY_SCAM, reasons shown, case cross-check says no payment pending |
| **Send borderline message** | Ambiguous message: NOT_SURE, never silently labelled safe |
| **Change payout account** | Held 48 hours, needs Zainab's PIN; account used by other claims is flagged |
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
| How do you stop a wrong name match? | Names alone never match. We need CNIC, or DOB plus husband/father name. Ambiguous cases ask for proof or go to a human. We show the false-match rate. |
| Is consent real or just UI? | Enforced in the API on every read; withdrawal blocks the next request; the blocked attempt is in the audit log. |
| Can the audit log be edited? | The app's DB role cannot UPDATE or DELETE it, and each row is hash-chained; `/audit/verify` detects tampering. |
| What about false alarms on real people? | We never auto-reject. Scam and document checks raise risk for a human; we publish false-alarm rates instead of claiming 100%. |
| What is real and what is simulated? | See the README table: government and payment services are mock; Jev, rules, consent, audit, auth are real. |
| Did you build this before? | All code was written during the event. Our FYP researched scam SMS detection; see PRIOR_WORK.md. |
| How would this scale or go real? | Mock services sit behind clean APIs and can be swapped for real ones; rules are data; tenants are separate departments. |
