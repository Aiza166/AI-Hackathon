# 01. The Idea

> PROTOTYPE ONLY. All people, records and services below are mock.

## The sentence

**We help widows claim their late husband's pension even though they can't read the forms, have a weak phone signal, their records spell names differently, and scammers and fake heirs target them.**

## Why this task

The brief asks for **one public task, finished end to end**, that serves three people:

- **The widow** cannot read forms and has a weak signal.
- **The shopkeeper** keeps getting fake "relief payment" messages.
- **The helper** serves 40 families from one shared phone.

A survivor pension claim is the widow's own story. It has a real approve/reject decision where **a wrong approval pays the wrong heir and hurts the real widow twice**. That is the brief's "one wrong approval can cost someone their savings", literally. All 8 technical challenges happen naturally inside this one flow, so we show them working instead of bolting them on.

Most teams will build a generic "relief payment" app because the brief names it. We use the same trust and scam knowledge (Scam Shield) but attach it to a deeper task.

## The story, step by step

Mock people: **Zainab Bibi** (widow), her late husband **Muhammad Aslam**, **Ayesha** (community helper), **Rafiq** (shopkeeper), **Kamran** (pension officer), plus an admin and an auditor.

### 1. Starting the claim
Zainab opens the app on a cheap phone, or Ayesha opens it for her in Helper Mode. Login is phone number + PIN (mock OTP). The first screen is big icons with an audio button that reads everything aloud in Urdu.

### 2. Telling the system what happened (voice + pictures)
- She taps the microphone and says in Urdu that her husband passed away. Speech-to-text **pre-fills** a structured claim form, and she confirms each field with a tap (we never trust speech blindly).
- She photographs the death certificate and her CNIC. OCR reads the fields.
- Every step is saved on the phone. If the signal drops, she continues later from the same spot. Nothing is lost or sent twice.

### 3. Checking facts against mock government services
- **Mock identity service (NADRA-like):** CNIC lookup and family record.
- **Mock death registry:** confirms the death.
- **Mock pension office:** finds Muhammad Aslam's pension.
- **Mock payment service (Raast-like):** confirms who owns the receiving account.

The mock records are deliberately messy: "Muhammad Aslam", "Mohd. Aslam" and "Muhammed Aslam" on different documents, a missing date of birth, a duplicate entry. There is also a **different** man called "Muhammad Aslam" with another CNIC, so a careless name match would pay the wrong family.

### 4. Safety checks
1. **Identity match:** fuzzy name matching **plus** CNIC and date of birth. A name alone never counts as a match.
2. **Duplicate claim check:** has someone else claimed this pension?
3. **Document check:** do the OCR fields agree with the registry? Are there signs the image was edited? (Shown to officers as risk indicators, never as a verdict.)
4. **Odd patterns:** is the payout account already used by other claims?

### 5. The decision: three outcomes
The engine combines **versioned eligibility rules** (stored in the database, editable by the admin) with a **confidence score**:

| Confidence | What happens |
|---|---|
| >= 0.95 and no red flags | Auto-approve |
| 0.70 to 0.95 | Ask for more proof, naming exactly which document |
| < 0.70, or any red flag | **"I am not sure"**: case goes to an officer with notes |

**The system never rejects anyone by itself.** Only a human can reject, because blocking a real widow is also a cost.

Why 0.95: we judge that a wrong approval costs about 20 times a short delay, so auto-approve only when `p > 20 / (20 + 1) = 0.952`. The evaluation page shows the full cost curve that backs this choice.

### 6. The explanation: two views
- **Zainab hears (Urdu audio + icon):** "Your claim is paused because another person has also claimed this pension. An officer will check within 3 days." (3 days is our mock service level; no official processing time exists.)
- **The auditor sees:** input, rule version, model version, confidence, every check result, the route and the final result.

### 7. Officer review
Kamran's queue is sorted by priority and confidence. He sees both claimants side by side, with the reason the system was unsure, and approves or rejects with a written reason. Everything is logged.

### 8. Safe payout (SafeSwitch)
- Money goes to Zainab's mock Raast account, after the payment service confirms the account is in her name.
- Any request to **change the payout account** (the most common way benefits are stolen) is held for 48 hours and needs Zainab's own confirmation by PIN or voice.
- If the new account already receives money for other claims, it is flagged at once and goes to an officer.

### 9. Scam Shield
- Rafiq (or anyone) forwards a message such as: "Your pension is released. Pay Rs 5000 processing fee at this link."
- The system checks small, observable facts (does it ask for a fee? an OTP? contain a link? claim to be from the government? come from an unofficial sender?) and gives a verdict: likely scam / looks genuine / not sure.
- It asks: **"Is someone on the phone telling you to do this right now?"** A yes raises the risk.
- **It cross-checks the person's real case:** "Your case shows no payment pending, and the government never charges a fee. This is a scam." A standalone scam detector cannot do this.
- False alarms are counted and shown honestly on the evaluation page.

### 10. Consent and take-back
- Zainab sees who can access her data and why: Ayesha (helper), the pension department, the auditor.
- She can turn individual items on or off, withdraw access, or ask for a correction.
- When she withdraws Ayesha's access, Ayesha's **very next request is blocked (403)** on the server, and the audit log shows the withdrawal and the blocked attempt.

### 11. Rules change live
- The admin publishes a real, dated rule change: **v2 = the federal 10-year cap** (effective 10 Sep 2024). After the spouse dies or becomes ineligible, other family members get the family pension for at most 10 years (children: 10 years or until age 21, whichever is later; disabled children: for life). People already drawing the pension before that date are exempt. No code change, no redeploy.
- **Digital Twin:** before publishing, the admin replays past cases under the new rule and sees "this would change 3 past decisions".
- Old decisions still show "decided under rule v1".

## Users and roles

| Role | Mock person | What they can do |
|---|---|---|
| Citizen | Zainab (widow), Rafiq (shopkeeper) | Start a claim, upload, use voice, track progress, check scam messages, control consent |
| Community helper | Ayesha (40 families, one phone) | Switch between families fast, act only where that family has given consent |
| Department officer | Kamran (pension department) | Review queue, approve or reject with reason, request proof |
| Admin | Admin | Users and roles, rule editor, Digital Twin, mock service controls |
| Auditor | Auditor | Read-only: audit log, consent records, every AI decision trace |

## What makes it win

- Every challenge in the brief is a natural step in one story, so the live demo shows behaviour, not claims.
- Thresholds come from a stated cost ratio and are backed by an evaluation page, not picked because they "sound right".
- "I am not sure" is a real route with reason codes, not a label.
- Jev is used as a **sensor** (small factual questions with probabilities). The decision stays in code and rules, so a scam message cannot argue its way to "safe".
- Judges can break it themselves from a judge console and then watch the audit replay.
