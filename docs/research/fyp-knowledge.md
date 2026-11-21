# What we learned from the prior study (FYP "Call and Link Scam Detection")

> Knowledge only. A team member's final year project (FAST-NUCES Karachi) studied scam SMS, WhatsApp
> messages, calls and links in Pakistan. We read its design paper, proposal, deck, architecture
> diagrams and repositories on 21 Nov 2026 to understand the ideas. **No code, model, prompt text,
> dataset row or asset from it is in this repository** (see `PRIOR_WORK.md`). Everything in Sahara was
> re-implemented from scratch during the hackathon. Any number below is a **prior study** figure,
> measured by the FYP on its own data, and is never presented as a Sahara result.

## 1. Architecture of the prior study

Three parts:

- **A phone app (Android)** that listened to incoming SMS, WhatsApp notification previews and the call
  state. From the call state it built two flags: "the sender is a saved contact" and "an unknown incoming
  call is ringing, active, or ended a short while ago". Only calls *to* the user counted; calls the user
  dialled never did.
- **A small relay server** between the phone and the AI decision model. It held the fixed question set,
  quoted the message as data, used a short timeout and returned only probabilities. It also expanded
  short links by following redirects (HEAD only, public IPs only).
- **An offline research pipeline** that audited public datasets, trained baselines and fitted thresholds.

Per message the phone ran: normalise the text, keyword rules, a URL check, the decision model through the
relay, then a risk score, and acted (allow, warn, or warn and hold links). The warning was a full-screen,
bilingual (English + Roman Urdu) page with the top two specific reasons and a "not a scam" button. A
local DNS-only blocker held suspicious hosts for a week.

There was no screenshot (OCR) input, no voice-note or call-recording transcription, no share-to-app
entry point and no second model in a cascade. Those are new in Sahara.

## 2. Signals used

**Text.** Invisible characters stripped, Unicode NFKC, Cyrillic/Greek look-alike letters folded, then
lowercase, then Roman Urdu spelling variants mapped to one form. Keyword groups covered: asking for a
code/PIN/CNIC, prizes, government schemes (BISP, Benazir, Ehsaas, Kafalat), "money sent by mistake",
account block threats, urgency, "call this mobile number", links, and wallet or bank brand names.

**Links.** A known bad-domain list; otherwise "risky" if the host was a raw IP, punycode, a known
shortener, a cheap top-level domain, a brand name inside a host that is not that brand's domain, or
written with look-alike letters (checked on the raw text, because normalising would turn the fake into
the real name). A small character-n-gram model on the host only added weak recall. HTTPS and path words
were not used, and URLs were deliberately kept out of the language model.

**Calls.** Only the two context flags above. Caller numbers were judged weak evidence because scammers
use SIMs registered to other people. The study discussed genuine short codes but did not build a
short-code allowlist.

## 3. How signals were combined

A hand-weighted formula in code: model probability, link score and keyword share averaged, plus a bonus
when an unknown call was in progress and a small discount for a saved contact, clamped to 0-1. The model
judged small facts; the decision was an inspectable formula with thresholds fitted on a validation split.
When the model failed, its term was dropped and separate offline thresholds applied.

Two lessons stand out:

1. **Fit thresholds for the exact score the app computes, separately for online and offline.** The app
   first shipped generic thresholds; offline it then warned on almost no scams, and online it flagged a
   large share of genuine Roman Urdu bank messages.
2. **How answers are combined matters as much as the questions.** Taking the maximum of many answers
   raised false alarms; a fitted combination fixed it.

## 4. Jev: strengths, weaknesses and question design

Jev (TypeSafe) answered English yes/no questions about each message.

- **One observable judgment per question.** Questions joined with "or" were worse; splitting them
  helped. Good questions describe what the message *does* (asks for a code, promises government money,
  threatens a block, tells you to call a number, pushes you to act now).
- **No identity questions in the score.** "Does it present itself as a bank or government?" is true of
  every genuine bank or government alert, so it inflated risk on real messages.
- **A benign indicator helps.** "Does it warn you never to share your code?" is typical of genuine OTP
  messages and pulled risk down.
- **Answers are nearly binary.** Most answers sat at the extremes, so thresholds and the "undecided" band
  need care. The study had no undecided band; Sahara has one (0.3-0.7 means "not sure").
- **Prompt injection had little effect** when the question set was fixed on the server, the message was
  quoted as data and only probabilities came back.
- **Fast and cheap, no training needed**, but out of the box it did not match a fine-tuned text encoder
  on the study's data (prior study). Paraphrased scams hurt keyword rules badly and Jev much less.
- **Language.** Questions in English worked on Roman Urdu after normalisation; Urdu script was out of
  scope in the study, so Sahara's Urdu-script cases are untested there.

## 5. Scam patterns in Pakistan (as described by the study and its sources)

- **Call + message combinations**: a prize or BISP message followed by a call from a fake official; a
  fake bank officer threatening a block while a *genuine* OTP arrives from the real short code; the
  victim reads out the code during the call.
- **Links** to fake JazzCash, Easypaisa or bank login pages, and links to APKs that read SMS and forward
  codes.
- **"Money sent by mistake"**: a fake wallet credit SMS and then a "please send it back" call.
- **Government scheme bait** (BISP, Benazir, Ehsaas) asking for CNIC and PIN through a look-alike link.
- Hard genuine cases: bank OTPs, wallet transfer confirmations, salary and bill alerts.
- Not covered by the study: police/FIA impersonation, WhatsApp account takeover by code theft, remote
  access apps, WhatsApp voice calls.

## 6. Evaluation approach

Public datasets were audited for duplicates and near-copies of an old UK spam set; two were kept (a
Roman Urdu phishing SMS set and an English Pakistani SMS set). Splits were grouped by message template
and frozen, thresholds were fitted on train/validation only, the test split was scored once, and false
alarm and miss rates were reported per source and per language. Robustness checks covered homoglyphs,
invisible characters, paraphrase and an injection suffix. The study also noted that a single small test
split hid large fold-to-fold instability (prior study). Its main limits: small templated data, no call
state in the data, and a planned real-world pilot that had not run.

## 7. What Sahara adopts, and how (all re-implemented)

| Idea from the prior study | In Sahara |
|---|---|
| The AI is a sensor; a formula in code decides | Already Sahara's rule. Scam Shield v2 keeps one inspectable score in `backend/app/services/scam.py`. |
| One observable judgment per question; no identity questions in the score | Question set `C-scam-v2`: new single questions (install an app or share the screen, link to log in or pay, call this number). `claims_government` only gates the "unofficial sender" signal and carries no weight. |
| A benign "warns not to share the code" indicator | Added as `warns_not_to_share` (recorded; used by the second sensor and in review). |
| Fixed questions on the server, message quoted as data | Jev gets the message under `untrusted_message`; the second sensor gets it between random per-request markers. |
| Link features: shortener, raw IP, punycode, cheap TLD, brand in a non-brand host, look-alike letters on the raw text, the "@" userinfo trick | `backend/app/scam/links.py`, written from scratch, plus typo distance, http vs https, login/payment words in the path, and a labelled allowlist (mock + real gov.pk / bisp.gov.pk style domains). |
| Do not trust caller ID | `backend/app/scam/calls.py`: an official short code is evidence, never proof; an official SMS code or helpline *calling you* is a red flag. |
| "Someone is on the phone with you" is a strong context signal | Kept and made a first-class step in the call flow. |
| Fit and report thresholds per mode (online vs offline) | The eval reports each sensor tier separately (deterministic only, Jev only, cascade) on Sahara's own invented set. |
| Report false alarms and misses per language | Kept, plus per channel (SMS, WhatsApp, call). |

Things we chose **not** to copy: following short links on the server (Sahara never fetches a link, to
avoid server-side request forgery and to avoid telling the scammer the link was opened), a DNS blocker,
and any trained model.

New in Sahara (not in the prior study): screenshot OCR intake, voice-note / call-recording transcription,
share-to-Sahara from WhatsApp/SMS, the second independent sensor cascade, and the same cascade on
document photos.
