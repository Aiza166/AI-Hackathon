# 02. Compliance Checklist (every requirement in the brief)

> Source: `AI_Hackathon_Problem_Statement.pdf`. "Demo proof" is what a judge sees live. Keep this table true: if something is cut, mark it here.

Legend: P = Planned, B = Built, T = Tested, X = Cut

## Constraints (section 03): all required

| Requirement | How we meet it | Demo proof | State |
|---|---|---|---|
| Wrong approvals cost more than slow ones | Cost ratio 20:1 gives auto-approve threshold 0.95; never auto-reject; any red flag goes to a human | Evaluation page: cost curve, wrong approvals = 0 on test set | B |
| Weak internet | Offline-first PWA, outbox with idempotency keys, saved progress, small pages, cached audio | Throttle to "Slow 3G", go offline mid-claim, come back, claim syncs once | P (server `Idempotency-Key` on `POST /cases` built and tested: replay, 422 on a changed body, 409 while in flight; frontend outbox in PR #3) |
| Low literacy | Icons, Urdu audio for every prompt, voice input confirmed by tap, minimal text | Complete a claim without reading | P |
| Rules change without notice | Rules are versioned JSON in the database (own small rules engine), edited by admin, no redeploy | Publish v2 (federal O.M. F.No. 9(3)R-6/2024-264, 10-09-2024: 10-year cap for heirs after the spouse) live; a new heir case (entitled after 10-09-2024) is capped under v2; an old heir case (entitled 2019) stays pinned to v1 | B (API, tested) |
| Bad data | Name normaliser + fuzzy match + CNIC/DOB agreement (never an auto-match without an exact CNIC); dedupe; missing fields lead to "ask for proof", never a crash | Muhammad/Mohd./Muhammed matched; the other Muhammad Aslam not matched | B |
| Explainable decisions | Two views: simple Urdu reason for the user, full trace for the auditor | Citizen hears reason; auditor opens trace | P |
| User control | Consent screen: see, share, withdraw, correct | Withdraw helper's access live | B (API) |
| "I am not sure" | Typed `UNSURE` route with reason codes, case notes, officer handoff | Second claimant appears, case pauses | B |

## User roles (at least 3): we use all 5

| Role | State |
|---|---|
| Citizen | B |
| Community helper | B |
| Department officer | B |
| Admin | B |
| Auditor | B |

## Core platform features: all required

| Feature | Where | State |
|---|---|---|
| Secure login (JWT) + role-based access, enforced on the server | FastAPI dependencies `get_principal()`, `require_role()` on every route | B |
| Dashboard with task progress, status, history | Citizen claim tracker; officer, admin, auditor dashboards | B |
| Case management (create, assign, escalate, close) | `cases` + case events; auto-assign to officer; escalate on UNSURE | B |
| Public REST API with API keys + Swagger/OpenAPI | FastAPI `/docs`; hashed API keys for outside systems | B |
| Audit log of every user, AI and agent action | Append-only `audit_events` with hash chain, `/audit/verify` | B |
| Consent management (see, share, withdraw, correct) | `consents` (artefact fields) + `assert_consent()` on every read | B (API) |
| Mock identity, payment and data services behind clean APIs | `/mock/nadra`, `/mock/death-registry`, `/mock/pension`, `/mock/raast` with failure injection | B |

## Platform features (pick at least 3): we plan 7

| Feature | State |
|---|---|
| Admin rule editor (change eligibility without code) | B (API) |
| Officer review queue with priority and confidence sorting | B |
| Low-bandwidth / offline mode | P |
| Notifications (in-app + mock SMS inbox) | P |
| Rate limiting and error handling | B |
| Multi-tenant workspaces (pension dept, social welfare dept) | B |
| Analytics dashboard per tenant (claims, routes, scam stats) | P |

## AI features (use at least 3): we plan 7

| AI feature | Where | State |
|---|---|---|
| Classification and routing (Jev) | Claim routing AUTO / ASK_PROOF / UNSURE; scam check | B |
| Guardrails + human approval | Never auto-reject; payout change needs confirmation; red flags go to officer | B |
| Explainability | Two-view explanations from reason codes | B |
| Voice | Urdu audio prompts; speech pre-fills fields (confirmed by tap) | P |
| Structured outputs | Voice/OCR into a validated Pydantic claim schema | P |
| Computer vision | OCR on CNIC/death certificate; edit-risk indicators | P |
| Anomaly detection | One payout account across many claims; repeated claims | P |
| Evaluation dashboard | Accuracy, false alarms, wrong approvals, UNSURE rate, speed, cost | P |

## Engineering basics

| Item | Plan | State |
|---|---|---|
| Database with migrations | Postgres + Alembic | B |
| Deployed link | Backend + DB on Railway (always on), frontend on Railway too (Vercel Hobby is non-commercial only; Cloudflare Pages is the fallback) | B (live) |
| Monitoring, logs, basic tests | Structured logs, Sentry, uptime ping, pytest on decision engine, RBAC, consent, matching | P |

## Technical challenges

| # | Challenge | Demo moment | State |
|---|---|---|---|
| 1 | Cost of being wrong | Cost curve + threshold justification on eval page | P |
| 2 | Saying "I am not sure" | Competing claimant: case pauses, officer gets notes | P |
| 3 | Bad data | Name variants matched; look-alike different person not matched; missing DOB asks for proof | P |
| 4 | Rules that change | Publish v2 live; v1 cases still show v1; Digital Twin preview | B (API, tested) |
| 5 | Explain and audit | Urdu reason for citizen; full trace + audit replay for auditor | P |
| 6 | Consent and take-back | Withdraw helper access: next request 403, logged | B (API, tested) |
| 7 | Works for everyone | Voice + icons on throttled network, offline resume | P |
| 8 | Scams and fake documents | Fee/OTP scam SMS flagged with case cross-check; edited certificate flagged; false-alarm rate shown | P |

## Bonus (optional)

| Feature | State |
|---|---|
| Digital Twin (replay rule change on past cases) | B (API, tested) |
| Helper Mode (one phone, many families, separate consent) | P |
| Offline-First Sync | P (part of core) |
| Scam Map (scam patterns by type, area, time) | P |

## Rules (section 06)

| Rule | How | State |
|---|---|---|
| Build during the event | Fresh repo, first commit after kickoff, no reused code | P |
| Mock all identity, payment, data | Mock services + generated fake seed data | P |
| Label as prototype | Banner on every page, README, API description | P |
| Tell judges what is real vs simulated | README table + demo "honest limits" slide | P |

## Submission (section 07)

| Item | Owner | State |
|---|---|---|
| Working prototype + live demo | both | P |
| GitHub repo link | Aiza | P |
| README | both | P |
| Demo video (public Google Drive link) | P2 | P |
| Slides (optional) | P2 | P |

## Honest limits (say these to judges)

- QR verification of death certificates is **not built and not confirmed**: no primary source confirms these certificates carry a QR code. We never show "QR verified".
- Document checks are risk indicators for an officer, never a "fake" verdict; missing EXIF is normal (WhatsApp strips it) and never counts against the claimant.
- Name-matching and scam error rates are measured on our synthetic / public sets, not on real NADRA data.
- Family pension amounts are mock values. "An officer will check within 3 days" is a **mock target**, not an official service level.
- Rule v2 models the federal civil-service family pension only. When a child's 10-year clock starts is our **assumption** (from the spouse's death or ineligibility); armed-forces coverage is unconfirmed; provincial rules differ.
- Scam Shield treats sender IDs (even BISP 8171) as evidence, never proof, because 8171 has been spoofed (PID PR No. 59, 5 July 2024).
- Urdu speech-to-text is only used to pre-fill fields that the user confirms with a tap.

## Open compliance risk

- **Prior work:** our FYP studied scam SMS detection with Jev. All code here is new; see `PRIOR_WORK.md`. Confirm with organizers in writing.
