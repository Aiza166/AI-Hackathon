# Screens (Stream C)

> PROTOTYPE. All names and numbers are mock. Every screen shows the PROTOTYPE banner at the top.
> Rough text sketches; a paper sketch photo (no people in it) can be added next to this file.

Rules every citizen screen follows: one question per screen, big buttons (>= 48px), pictogram + Urdu + English + audio button, voice only pre-fills a field the user confirms with a tap.

## Screen list

| # | Screen | Who | Status |
|---|---|---|---|
| 1 | Login (phone + PIN; demo personas behind a hidden "Demo accounts (mock)" toggle) | all | built (`Login.tsx`) |
| 2 | Citizen home (my claims, start claim, my data) | citizen | built, SVG pictograms done; "check a message" (Scam Shield) not built yet |
| 3 | Helper Mode family picker + "now acting for: X" banner | helper | built: consent filter (families without consent are locked), lock note, acting-for banner |
| 4 | Claim step 1: relation (widow / son / daughter) | citizen, helper | built |
| 5 | Claim step 2: deceased name | citizen, helper | built |
| 6 | Claim step 3: deceased CNIC (optional, its own step) | citizen, helper | built |
| 7 | Claim step 4: documents I have | citizen, helper | built |
| 8 | Claim step 5: payout account | citizen, helper | built |
| 9 | Claim step 6: review and send (+ "saved on this phone / waiting to send" state) | citizen, helper | built; offline outbox in PR #3 (`feat/c-offline-outbox`) |
| 10 | Decision result (icon + Urdu reason + audio, what happens next) | citizen | built (`CaseResult.tsx`) |
| 11 | My data: who can see it, withdraw, request correction, who saw it | citizen | built (`MyData.tsx`) |
| 12 | Officer queue (priority + confidence, case detail + decision trace, approve/reject with reason) | officer | built (`OfficerHome.tsx`) |
| 13 | Auditor log (filter) + verify chain | auditor | built (`AuditorHome.tsx`) |
| 14 | Admin rules (versions, draft) + Digital Twin table + publish | admin | built (`AdminHome.tsx`) |
| 15 | Scam Shield, Scam Map, SafeSwitch, Eval page, Judge console, Audit replay | various | Phase 3 (Scam Shield, Scam Map and SafeSwitch APIs are ready) |

The claim wizard has 6 steps (one question per screen).

## Sketches

### Citizen home
```
[ PROTOTYPE banner                         ]
Sahara                         Zainab · (exit)
+----------------+  +----------------+
|   [document]   |  |   [message?]   |
|  نیا دعویٰ       |  |  پیغام چیک کریں  |
|  New claim  🔊 |  |  Check msg  🔊 |
+----------------+  +----------------+
+----------------+  +----------------+
|   [clock]      |  |   [lock]       |
|  میرا دعویٰ      |  |  میرا ڈیٹا       |
|  My claim   🔊 |  |  My data    🔊 |
+----------------+  +----------------+
[ (cloud) 1 step waiting to send · Send now ]
```

### Claim step (one question)
```
[ PROTOTYPE banner ]
Step 1 / 6 · for Zainab        (o o o o o o)
آپ مرحوم کی کون ہیں؟                 [ 🔊 ]
+----------+ +----------+ +----------+
| [widow]  | | [son]    | | [daughter]|
|  بیوہ     | |  بیٹا     | |  بیٹی      |
+----------+ +----------+ +----------+
[ ⬅ Back ]                 [ Next ➡ ]
(saved on this phone ✓)
```

### Decision result
```
[ PROTOTYPE banner ]
      [ big pictogram: check / pause / question ]
  آپ کا دعویٰ منظور ہو گیا ہے                 [ 🔊 ]
  Your claim is approved.
  What happens next: money to account ending 0001
  Reference: SAH-000123        [ Back home ]
```

### Officer queue
```
[ PROTOTYPE banner ]
Queue (sorted by priority, then confidence)
| Ref       | Route   | Conf | Reasons            | |
| SAH-0007  | UNSURE  | 0.41 | COMPETING_CLAIM    |>|
Selected case: claimant A | claimant B side by side
Why the system was unsure: ...
[ Approve ] [ Reject (reason required) ] [ Ask for proof ]
```
