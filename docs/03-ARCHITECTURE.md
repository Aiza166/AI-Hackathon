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

Example ruleset `survivor-pension` v1 (exact rules finalised from research):

1. Deceased must be a registered pensioner in the pension office.
2. Death must be confirmed by the death registry.
3. Claimant must be listed as spouse in the family record.
4. Claimant must not have remarried (v1). **v2 changes this:** remarried widows remain eligible.
5. Claim must be filed within N years of death.
6. Payout account must be in the claimant's own CNIC.

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
