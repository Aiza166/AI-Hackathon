# 03. Architecture

> PROTOTYPE ONLY. All external government and payment services are mock services inside this project.

## Design principles

1. **Jev is a sensor, code decides.** Jev answers small, observable yes/no or choice questions with probabilities. Versioned rules and code-side thresholds make the decision. A scam message or an edited document cannot "argue" its way to approval.
2. **Never auto-reject.** The system may auto-approve, ask for proof, or hand to a human. Only an officer can reject.
3. **Every decision is reproducible.** Each decision stores input hash, rule version, model ID, raw probabilities, thresholds used, route and reason codes.
4. **Consent is enforced in the API**, in one function every data read passes through. The UI only reflects it.
5. **Offline first.** The phone keeps working without signal; the server deduplicates on sync.
6. **Fail safe, not silent.** If Jev or a mock service is down or slow, money never moves automatically: the case routes to `UNSURE` with reason `SERVICE_UNAVAILABLE`.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Backend API | Python 3.12, FastAPI, Pydantic v2 | Swagger/OpenAPI for free; Jev SDK, OCR, rapidfuzz, ZEN all Python |
| Database | PostgreSQL 16 + SQLAlchemy 2 + Alembic migrations | Required by brief; JSONB for traces |
| Rules engine | GoRules ZEN (`zen-engine`), rules stored as versioned JSON rows | Edit rules without redeploy; React editor exists |
| AI decision model | Jev via TypeSafe API (`typesafe-sdk`), pinned `jev-1.14.0` | Typed questions, calibrated probabilities; brief names Jev |
| Name matching | rapidfuzz + our own normaliser for Pakistani name variants | Fast, testable, explainable |
| OCR / documents | Tesseract (`pytesseract`) + OpenCV; Pillow for EXIF; simple error-level analysis | Free, local, enough for mock documents |
| Speech | Pre-generated Urdu audio (Azure `ur-PK-UzmaNeural`) for fixed prompts, cached in the PWA; speech-to-text (Whisper or Google `ur-PK`) only pre-fills fields | Reliable offline demo; no blind trust in STT |
| Frontend | React + Vite + TypeScript PWA, Tailwind, Dexie (IndexedDB) outbox, Workbox service worker | Offline, small, installable |
| Auth | JWT (access + refresh) issued by our API, bcrypt PINs/passwords; hashed API keys for outside systems | Simple, fully under our control, server-side RBAC |
| Background jobs | arq on Redis (payout hold timer, webhook delivery, notifications) | Brief option "background jobs and queues" |
| Rate limiting | `slowapi` | Per-IP and per-key limits |
| Observability | Structured JSON logs, Sentry, uptime ping, Langfuse optional for Jev calls | Brief: monitoring and logs |
| Hosting | Railway (API + Postgres + Redis, always on), Vercel (PWA) | No cold starts during judging |
| Tests | pytest (unit + API), Playwright (E2E golden path) | Brief: basic tests; ECC e2e-runner |

## Components

```
  Citizen / Helper --> +-------------------------------+
  Officer / Admin  --> |  PWA (React, offline outbox)  | <-- cached Urdu audio, icons
  Auditor / Judge  --> +---------------+---------------+
                                       | HTTPS (JWT) / API key
                       +---------------v---------------+
                       |        FastAPI  /api/v1        |
                       |  auth | RBAC | consent guard   |
                       |  rate limit | audit middleware |
                       +--+--------+--------+-------+---+
                          |        |        |       |
                 +--------v--+ +---v---+ +--v----+ +v---------------+
                 | Cases     | | Rules | | Scam  | | Payout         |
                 | (claims,  | | (ZEN) | | Shield| | (SafeSwitch)   |
                 |  docs)    | +---+---+ +--+----+ +-------+--------+
                 +-----+-----+     |        |              |
                       |     +-----v--------v------+       |
                       +---> |   Decision engine   | <-----+
                             | signals -> rules -> |
                             | Jev -> conf -> route|
                             +----+------------+---+
                                  |            |
                        +---------v----+  +----v--------------------+
                        | Jev (TypeSafe)|  | Mock services           |
                        | pinned model  |  | NADRA-like, death reg., |
                        +---------------+  | pension, Raast-like     |
                                           | (+ failure injection)   |
                                           +-------------------------+
        Postgres: cases, decisions, rule_versions, consents,
        audit_events (append-only, hash chain), mock_* tables
        Redis: job queue (payout holds, notifications, webhooks)
```

## Decision engine

### Step 1: gather signals (all in code except where Jev is named)

| Signal | Source | Output |
|---|---|---|
| `identity_match` | Name normaliser + rapidfuzz + CNIC + DOB vs mock NADRA | score 0-1 + which fields agreed |
| `relationship_ok` | Mock family record: is claimant the deceased's spouse? | yes / no / unknown |
| `death_confirmed` | Mock death registry | yes / no / unknown |
| `pension_found` | Mock pension office | pension record or none |
| `duplicate_claim` | Other open/approved claims on the same pension | count |
| `doc_consistency` | OCR fields vs registry (name, CNIC, date of death) | score 0-1 |
| `doc_edit_risk` | EXIF, error-level analysis, field checks | low / medium / high indicators |
| `account_owner_ok` | Mock Raast title fetch: account in claimant's CNIC? | yes / no |
| `account_reuse` | Same payout account on other claims | count |
| `jev_doc_checks` | **Jev** Nouls on the document image (see Step 3) | probabilities |
| `service_health` | Did every mock service and Jev answer in time? | ok / degraded |

### Step 2: eligibility rules (GoRules ZEN, versioned)

Ruleset `survivor-pension` (grounded in Pakistan family pension rules; see `docs/research/survivor-pension.md` section 1):

| Rule | v1 | Basis |
|---|---|---|
| R1 Spouse first | Widow is eligible if the family record (FRC) links her to the deceased, nikah nama present, death verified | Rule 4.10, SHC order 2025 |
| R2 Share split | n = widows + eligible children; if n <= 4 equal shares, else each widow 1/4 and children split the rest | Rule 4.10 (we pick the "n <= 4" reading and say so) |
| R3 Child age | Son over 25 and not disabled: not eligible | Rule 4.10 (Sindh text) |
| R4 Daughter status | Unmarried, widowed or divorced daughter eligible until remarriage; divorce date irrelevant | SC ruling 30 Jul 2025 |
| R5 Required documents | Death certificate, claimant CNIC, FRC, nikah nama (widow), bank account titled to claimant; missing item = `missing_info` naming it | Pension / EOBI forms |
| R6 Single pension | Already drawing a family pension: not eligible | Federal rule |
| **R7 (v2 only)** | **10-year cap for non-spouse heirs** after the spouse dies or becomes ineligible, if they became eligible on or after 2024-09-10; child = max(10 years, until 21); disabled child = life; existing pensioners exempt | Finance Division OM F.No.9(3)R-6/2024, 10 Sep 2024 |

A second widow who **is** in the FRC is a lawful co-sharer (R2), not a fraud flag. A claimant who is **not** in the FRC is a red flag. Family pension amounts in the mock are made up and labelled, because no source gives the rate.

The rules return `eligible | not_eligible | missing_info` plus the list of rules that fired. Rules never reject on their own: `not_eligible` routes to an officer with the reason.

### Step 3: Jev questions (sensor only)

Pinned model `jev-1.14.0`; the `model` field from every response is stored. All questions about one input are bundled in one request.

Document image (death certificate):

- Noul: "Is there an official stamp or seal on this document?"
- Noul: "Is any text on this document covered, smudged or overwritten?"
- Noul: "Is the name of the deceased on the document a spelling of 'Muhammad Aslam'?"

Intake routing from a voice transcript (pre-fill only):

- Choice: "What does the person want?" options: new pension claim / check claim status / report a suspicious message / change payout account / something else
- Companion Noul: "Does any of these options fit what the person said?"

Scam Shield (forwarded message), bundled Nouls:

- Does the message ask for a fee or payment?
- Does it ask for an OTP, PIN or password?
- Does it contain a link?
- Does it claim to come from a government office?
- Does it create urgency (deadline, threat, prize)?

Deterministic checks stay in code, never in Jev: sender ID against the official sender list, link domain against official domains and a bad-domain list, all dates and amounts.

Jev band rule (from TypeSafe guidance): a Noul probability above 0.7 counts as yes, below 0.3 as no, and between 0.3 and 0.7 is **undecided**, which raises `JEV_UNDECIDED`.

### Step 4: confidence and route

```
hard_flags = duplicate_claim > 0
           or account_reuse > 0
           or doc_edit_risk == high
           or rules == not_eligible
           or any money-relevant Jev Noul undecided
           or service_health == degraded

if rules == missing_info:       route = ASK_PROOF    # name the exact document
elif hard_flags:                route = UNSURE       # officer, with reason codes
else:
    p = min(identity_match, doc_consistency, relationship_certainty)   # conservative
    if p >= T_AUTO (0.95):      route = AUTO_APPROVE
    elif p >= T_HUMAN (0.70):   route = ASK_PROOF
    else:                       route = UNSURE
```

Thresholds live in the ruleset, so they are versioned and editable too.

### Why 0.95 and 0.70 (Challenge 1)

- Cost of a wrong approval `C_wrong` = 20 units (wrong heir paid, recovery effort, real widow delayed further, lost trust). Cost of a delay `C_delay` = 1 unit (one more week of waiting).
- Auto-approving is worth it only when the expected cost of approving is lower than the expected cost of waiting: `(1 - p) * C_wrong < p * C_delay`, which gives `p > C_wrong / (C_wrong + C_delay) = 0.952`.
- Below 0.70, one more document rarely resolves the doubt in our test set, so a human looks at it directly.
- The evaluation page **sweeps T_AUTO from 0.50 to 0.99** on the labelled mock case set and plots total cost, wrong approvals and average delay, so judges see that 0.95 sits near the lowest-cost point.

### Step 5: explanation

Reason codes map to fixed, pre-written Urdu and English sentences with icons and pre-generated audio. There is no free-text generation, so nothing unsafe or wrong is said to the citizen.

| Reason code | Citizen hears (English meaning) |
|---|---|
| `DUPLICATE_CLAIM` | Another person has also claimed this pension. An officer will check within 3 days. |
| `NAME_MISMATCH` | The name on your documents does not clearly match the records. Please upload a clearer photo or show your CNIC to the helper. |
| `MISSING_DEATH_CERT` | We need a photo of the death certificate. |
| `ACCOUNT_NOT_OWNED` | The bank account is not in your name. Please give an account in your own name. |
| `SERVICE_UNAVAILABLE` | We could not reach a government record right now. Your claim is saved and an officer will continue it. |
| `APPROVED` | Your claim is approved. The first payment will reach your account by date X. |

The auditor view shows the full decision row plus every audit event for the case.

## Name matching (Challenge 3)

1. Normalise: lowercase, unify Unicode, remove punctuation; canonicalise `mohd`, `muhammad`, `mohammad`, `muhammed`, `m.` to one token; drop relationship markers (`s/o`, `w/o`, `d/o`, `bin`, `bint`) and honorifics (`mr`, `mst`), treat `bibi` as an optional token.
2. Compare: rapidfuzz `token_sort_ratio` and Jaro-Winkler on normalised names.
3. **Never match on name alone.** A match needs a high name score **and** an exact CNIC, or a high name score plus exact DOB plus agreeing father/husband name.
4. Ambiguous (name close, other fields missing or conflicting): `NAME_MISMATCH`, routed to ASK_PROOF or UNSURE.
5. Measured on a synthetic pair set (same-person variants vs different people with similar names): the eval page shows false-match and missed-match rates.

## Rules versioning and Digital Twin (Challenge 4)

- `rule_versions` rows are immutable once published. Publishing v2 creates a new row and marks it live; v1 stays.
- Every decision stores `rule_version_id`.
- The admin edits in a form or the ZEN JSON editor, saves a draft, and runs **Digital Twin**: re-run the last N decided cases with the draft (no writes, no payouts) and show which outcomes would change and why. Then publish.
- Publishing is audited (who, when, diff).

## Consent (Challenge 6)

Consent record, modelled on India's Account Aggregator consent artefact:

| Field | Example |
|---|---|
| `subject_person_id` | Zainab |
| `grantee` | helper Ayesha / pension department / auditor |
| `purpose` | file and track survivor pension claim |
| `fields` | cnic, family_record, death_certificate, payout_account |
| `valid_until` | date |
| `status` | active / withdrawn |

- Every read of personal data goes through `assert_consent(principal, subject, field, purpose)`. No consent: HTTP 403 plus audit event `CONSENT_DENIED`.
- Withdrawal takes effect on the next request (consent decisions are never cached).
- Correction: the citizen files a correction request, an officer approves it, and the old value is kept in history.
- A "Who saw my data" screen lists every access from the audit log, with a "report misuse" button.

## Audit log (Challenge 5)

- Table `audit_events` is append-only: UPDATE and DELETE are revoked from the app's database role.
- Each row: `seq, ts, actor_type (user|ai|system|agent), actor_id, role, action, resource, case_id, details jsonb, prev_hash, hash`, where `hash = sha256(prev_hash + canonical_json(row))`.
- `GET /api/v1/audit/verify` recomputes the chain and reports the first broken row, if any.
- Logged: logins, every read of personal data, every decision (AI actor), every Jev call (model ID, latency), rule publishes, consent changes, payout changes, blocked attempts.

## Offline and low bandwidth (Challenge 7)

- PWA first load under 200 KB gzipped; icons as an SVG sprite; small audio clips (Opus).
- Each claim step is saved in IndexedDB (Dexie). Actions go to an **outbox** with a client-generated idempotency key. The server stores keys and ignores repeats, so retries never duplicate.
- Sync on reconnect plus a manual "send now" button (the Background Sync API is Chromium-only, so we don't rely on it).
- Small JSON responses; images compressed on the phone before upload.

## Scam Shield (Challenge 8) and Scam Map (bonus)

- Input: forwarded text, sender ID, optional "is someone on the phone with you?" answer, optional area.
- Score: Jev Nouls (fee, OTP, link, claims to be government, urgency) + code checks (unofficial sender, unofficial domain) + the phone-pressure answer + **case cross-check** (no payment pending on their case).
- Verdict: `LIKELY_SCAM / LOOKS_GENUINE / NOT_SURE`, with reason sentences.
- Every check is stored (normalised text, no phone numbers shown) and aggregated into the **Scam Map**: counts by scam type, area and hour.
- The eval page shows false-alarm and miss rates on a labelled message set built from public examples.

## SafeSwitch payout

- Payout account change: check the owner CNIC via the mock Raast title fetch, check `account_reuse`, then hold 48 hours (background job) and require the citizen's own PIN or voice confirmation.
- A helper can start a change but cannot confirm it.
- Any flag goes to officer review. Every step is audited. The citizen is notified on request and on completion.

## Mock services

| Service | Endpoints (under `/mock/...`) | Notes |
|---|---|---|
| NADRA-like identity | `GET /persons/{cnic}`, `GET /family/{cnic}` | Seeded with messy names, missing DOBs, a duplicate person |
| Death registry | `GET /deaths/{cnic}` | Includes one record with a wrong date |
| Pension office | `GET /pensions/{cnic}` | Monthly amount, status |
| Raast-like payments | `GET /accounts/{iban}/title`, `POST /payments` | Returns the account holder's CNIC; payment receipts |
| Failure injection | `POST /mock/admin/faults` | Admin or judge can add latency or errors per service |

Mock services are separate modules with their own tables and clean APIs, so they could be swapped for real ones.

## Data model (main tables)

| Table | Key columns |
|---|---|
| `tenants` | id, name (Pension Department, Social Welfare Department) |
| `users` | id, tenant_id, role, name, phone, pin_hash, person_id (citizens) |
| `api_keys` | id, tenant_id, key_hash, scopes, created_by, revoked_at |
| `persons` | id, cnic, display_name |
| `helper_assignments` | helper_user_id, person_id |
| `cases` | id, tenant_id, type, claimant_person_id, deceased_cnic, status, priority, assigned_officer_id, created_by, created_at |
| `case_documents` | id, case_id, kind, storage_key, ocr_json, edit_risk_json |
| `case_events` | id, case_id, kind (created, assigned, escalated, proof_requested, approved, rejected, closed), actor, note |
| `decisions` | id, case_id, rule_version_id, model_id, input_hash, signals jsonb, jev_raw jsonb, confidence, thresholds jsonb, route, reason_codes[], explanation_key, created_at |
| `rule_versions` | id, ruleset, version, zen_json, thresholds jsonb, status (draft/live/retired), created_by, published_at |
| `consents` | id, subject_person_id, grantee_type, grantee_id, purpose, fields[], valid_until, status, withdrawn_at |
| `correction_requests` | id, person_id, field, old_value, new_value, status |
| `audit_events` | seq, ts, actor_type, actor_id, role, action, resource, case_id, details, prev_hash, hash |
| `payout_accounts` | id, person_id, iban, verified_owner_cnic, status |
| `payout_change_requests` | id, person_id, new_iban, requested_by, hold_until, confirmed_at, status, flags |
| `scam_checks` | id, text_norm, sender_kind, signals jsonb, verdict, confidence, area, created_at |
| `notifications` | id, user_id, channel, template_key, payload, sent_at |
| `webhooks` | id, tenant_id, url, secret_hash, events[] |
| `idempotency_keys` | key, user_id, response_hash, created_at |
| `mock_*` | mock_persons, mock_family, mock_deaths, mock_pensions, mock_accounts, mock_faults |

## API outline (`/api/v1`)

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout` |
| Cases | `POST /cases`, `GET /cases`, `GET /cases/{id}`, `POST /cases/{id}/documents`, `POST /cases/{id}/submit`, `POST /cases/{id}/assign`, `POST /cases/{id}/escalate`, `POST /cases/{id}/close` |
| Officer | `GET /queue` (priority + confidence sort), `POST /cases/{id}/approve`, `POST /cases/{id}/reject`, `POST /cases/{id}/request-proof` |
| Decisions | `GET /cases/{id}/decisions`, `GET /decisions/{id}/trace` (auditor), `GET /decisions/{id}/explain` (citizen) |
| Consent | `GET /me/consents`, `POST /me/consents`, `POST /me/consents/{id}/withdraw`, `POST /me/corrections`, `GET /me/access-log` |
| Helper | `GET /helper/families`, `POST /helper/switch/{person_id}` |
| Payout | `POST /me/payout/change`, `POST /me/payout/change/{id}/confirm` |
| Scam Shield | `POST /scam/check`, `GET /scam/map` |
| Rules | `GET /rules`, `POST /rules/drafts`, `POST /rules/drafts/{id}/simulate` (Digital Twin), `POST /rules/drafts/{id}/publish` |
| Audit | `GET /audit`, `GET /audit/verify`, `GET /cases/{id}/replay` |
| Eval | `POST /eval/run`, `GET /eval/latest` |
| Admin | users, roles, API keys, tenants, webhooks, `POST /admin/judge/*` (judge console actions), `POST /admin/seed/reset` |
| Analytics | `GET /analytics/tenant` |
| Health | `GET /healthz`, `GET /readyz` |

All responses use one envelope: `{ "success": bool, "data": ..., "error": null | {code, message}, "meta": {...} }`.

## Security checklist

- RBAC enforced in FastAPI dependencies on every route; tests cover a full role x endpoint matrix.
- Consent enforced in `assert_consent()`; tests cover "withdraw, then read = 403".
- Passwords and PINs hashed with bcrypt; API keys stored hashed; short-lived JWTs with refresh.
- Pydantic validation on every request body; uploads limited by size and type.
- Rate limits on login, scam check and the public API.
- Secrets only from environment variables; `.env.example` lists names only.
- CORS restricted to our frontend origin.
- Errors never leak stack traces or other people's data.
- Run the ECC `security-reviewer` agent before each merge to `main`.

## Repo layout

```
backend/
  app/
    api/         routers per area
    core/        config, security, auth, consent guard, audit, rate limit
    decision/    signals, matching, jev client, rules (ZEN), router, explanations
    services/    cases, payout, scam shield, notifications, webhooks
    mock/        mock NADRA, death registry, pension, Raast + fault injection
    models/      SQLAlchemy models
    schemas/     Pydantic schemas
  alembic/       migrations
  tests/
  scripts/       seed data generator, eval runner, audio generator
frontend/
  src/
    pages/       citizen, helper, officer, admin, auditor, judge console, eval, scam map
    offline/     Dexie db, outbox, sync
    audio/       cached Urdu clips
docs/
```

## Research-driven details (Sat 21 Nov; these win where earlier sections differ)

Source: [docs/research/survivor-pension.md](research/survivor-pension.md).

### Name matching pipeline
| Stage | Design |
|---|---|
| Parse | Split on s/o, w/o, d/o, bin, bint, ibn. Move honorifics (Syed, Sheikh, Haji, Chaudhry, Malik, Begum, Bibi, Mst) to a low-weight field. |
| Canonicalise | Mohd, Md, M., Mohammad, Mohammed, Muhammed map to `muhammad`; expand "M." only if the other record has a Muhammad-family token. |
| Block | CNIC exact, OR key token + birth year, OR phonetic key + district. Phonetic codes only **propose** pairs, never count as evidence. |
| Score | Fellegi-Sunter style: sum log2(m/u) per field; `muhammad` down-weighted (term frequency). Name `token_sort_ratio` bands >=95 / 85-95 / 70-85 / <70; CNIC exact / one-digit typo / different / missing; DOB exact / year / +-1 / different / missing. Never `token_set_ratio`. |
| Route | p >= 0.95 **and exact CNIC** and no flag: match. 0.70-0.95: ask for the missing field. < 0.70, CNIC conflict, or two candidates above 0.70: UNSURE. **No auto-match without exact CNIC.** |

- The CNIC father/husband field is weak evidence: since 2021 married women may keep their father's name there, so Zainab's CNIC may not name Aslam.
- NADRA CNIC DOB is the single source of truth (EOBI paid Rs2.79bn on altered ages from other documents).
- Eval: ~500 synthetic identities with variants + hard negatives (same full name, same name + birth year, siblings, CNIC one digit off). Threshold set where false-match rate on hard negatives = 0; plot false-match, false-non-match, UNSURE rate, blocking recall.

### Payout safety (SafeSwitch + Confirmation of Payee)
- Before any payout: mock Confirmation-of-Payee check on the account title: **match = proceed, close match = ASK_PROOF, no match = UNSURE**.
- Account change hold: **48 hours**, extended to **4 business days** when a red flag fires (account used by another claim, CoP close/no match, change soon after the death is reported). Context: SSA moved to 1 business day; UK firms may delay at most 4 business days.
- Confirmation (PIN/voice) goes to the widow directly, never to the helper's phone.
- Cross-check "already drawing a family pension / excluded" before approval (R6).

### Document checks = indicators, never a verdict
Ranked by evidence, each shown with its evidence and a "what this cannot tell" line, labelled "needs a second look", never "fake", never rolled into one score:
1. OCR fields (CNIC 13 digits, DOB, date of death, names) cross-checked with registry by CNIC + DOB. **Strongest signal.**
2. Copy-move (ORB/SIFT keypoints) on seal/stamp regions only.
3. ELA on the original upload, shown next to the image.
4. EXIF as context only; **missing EXIF never counts against anyone**.
5. Optional QR decode; "no QR found" is neutral. We never show "QR verified".
- Officer agree/disagree with each indicator is logged for the eval page.
- Mock image set: each image as original, WhatsApp-recompressed, and screenshot.

### Jev usage rules
- Images/Box need header `TypeSafe-Danger-Zone-Images: true`. PNG/JPEG only, each side 280-1568 px, 78,400-2,458,624 pixels, 16 MiB per file, 32 MiB per request; out-of-range images fail the whole request. Rotate pixels (EXIF orientation is stripped), fit to 1568 px, baseline JPEG, fresh UUID per image.
- Box always returns a box: pair it with a presence Noul.
- Choice: act only if its companion Noul > 0.7 **and** top choice probability > 0.7; otherwise a person decides.
- Split reading from judging (read the date in one question, judge it in code).
- Page check + crop check for OCR fields; flag if either < 0.25.
- Untrusted text goes under a labelled state key (`untrusted_message`); add an `addresses_reader_instructions` Noul as an injection sensor.
- Log model, usage, every probability, question-set version, image SHA-256 (not the image), thresholds, route. Measure image latency p50/p95; timeout = UNSURE.
- Question sets: A intake (text), B document (image), C scam SMS (text) as in the research report section 6.

### Scam Shield weighting
Content rules (asks fee, asks code, link, unverified "payment ready" claim) outweigh sender ID. Official short codes (e.g., BISP 8171) are **evidence, never proof**: 8171 masking has been reported (PID, 5 Jul 2024). The app uses mock senders; real short codes appear only in the README as real-world patterns.

### Offline and size budgets
- Citizen shell <= 170 KB total (JS <= 100 KB), each later screen <= 30 KB, each audio clip ~15 KB, photos compressed on device to ~200 KB (from web.dev slow-3G budget).
- ~60 prompts pre-generated with Azure `ur-PK-UzmaNeural` (~6,000 characters, inside the free tier).
- Outbox key = UUID created when the user taps save. Flush on app open, `online` event, Background Sync (Chromium only) and a "Send now" button. Call `navigator.storage.persist()`.
- Server Idempotency-Key (IETF draft): unique per principal, replay stored response, 422 if the same key comes with a different body, 409 while in flight.
- Outbox partitioned per family in Helper Mode.
