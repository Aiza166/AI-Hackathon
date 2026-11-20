# 04. Build Plan

> Full scope as planned for a 3-4 person team. We are 2 people, each driving Claude Code agents in parallel, so the work is split into 4 streams and each person owns 2.

Build window: **Fri 20 Nov 18:00 to Sun 22 Nov 18:00 PKT**. Submit by **Sun 17:30** (30 min buffer). Judging: Mon 23 Nov.

## The 4 work streams

| Stream | Scope | Owner | Claude helpers (ECC) |
|---|---|---|---|
| **A. Platform & security** | Migrations, JWT auth, RBAC, API keys, tenants, cases + case events, consent + `assert_consent()`, audit hash chain, rate limiting, notifications, webhooks, background jobs, deploy | Aiza | `planner`, `tdd-guide`, `security-reviewer`, `database-reviewer` |
| **B. Decision & AI** | Mock services + messy seed generator, name matching, ZEN rules + versions + Digital Twin, Jev client, OCR + document checks, decision router, explanations, Scam Shield, eval set + eval runner | Aiza | `tdd-guide`, `python-reviewer`, `fastapi-reviewer` |
| **C. Frontend PWA** | Citizen voice/icon flow, offline outbox, Helper Mode, officer queue, admin rule editor + Digital Twin screen, auditor trace + replay, consent screens, Scam Shield + Scam Map, analytics, eval page | Teammate | `react-reviewer`, `a11y-architect`, `typescript-reviewer` |
| **D. Demo & quality** | Seed personas, judge console, Urdu audio clips, RBAC test matrix, Playwright E2E, monitoring, README, demo video, slides, Q&A prep | Teammate (Aiza helps on tests) | `e2e-runner`, `doc-updater`, `verification-loop` |

Swap streams if skills fit better. Each person runs 1-2 Claude Code sessions at a time, one per stream, each in its own branch or git worktree so they don't collide.

## Contracts first (so streams don't block each other)

Before splitting, agree and commit these (Phase 0):

1. `docs/03-ARCHITECTURE.md` API outline and response envelope (done).
2. `backend/app/schemas/` Pydantic models for Case, Decision, Consent, ScamCheck, RuleVersion. The frontend generates TypeScript types from the OpenAPI spec (`openapi-typescript`).
3. Reason codes list + Urdu/English sentences (`backend/app/decision/explanations.py`), shared with the frontend for audio file names.
4. Seed personas (Zainab, Ayesha, Rafiq, Kamran, admin, auditor + 40 helper families + traps).

The frontend works against a mock server (MSW) built from the OpenAPI spec until the real endpoints land.

## Timeline (PKT)

### Phase 0: Foundations. Sat 00:30 to 03:00
| Task | Stream | Done when |
|---|---|---|
| Repo scaffold: `backend/` (FastAPI, Alembic, pytest), `frontend/` (Vite React PWA), CI running tests | A + C | Both run locally; CI green |
| Get Jev key, read rate limits in console, pin `jev-1.14.0`, one logged call | B | `model` field logged |
| Roman Urdu / Urdu smoke test: 20 messages through 5 Nouls | B | Go / no-go note in STATUS.md |
| Send organizer email about prior work (FYP), save reply | D | Email sent |
| Contracts above committed | all | Schemas + reason codes merged |

**Sleep Sat 03:00 to 08:30.**

### Phase 1: Golden path, thin but end to end. Sat 09:00 to 15:00
| Task | Stream | Done when |
|---|---|---|
| Schema + migrations for all main tables, seed script with messy data | A + B | `make seed` resets everything |
| JWT login, roles, `require_role()`, RBAC test matrix | A | Citizen token gets 403 on officer route, logged |
| Audit middleware + hash chain + `/audit/verify` | A | Verify passes; tampered row detected in a test |
| Mock NADRA, death registry, pension, Raast APIs | B | Endpoints return seeded messy data |
| Decision engine v0: signals, rules v1 in ZEN, router, reason codes | B | Zainab's clean claim auto-approves; duplicate claim routes UNSURE |
| Citizen claim flow (icons + audio), officer queue, approve/reject | C | Claim filed in UI appears in officer queue |
| Deploy: Railway (API + Postgres + Redis), Vercel (PWA), uptime ping | D | Public URLs work from a phone on mobile data |

**Milestone M1 (Sat 15:00):** a judge could watch a claim go from the citizen's phone to an officer decision on the deployed URL in under 90 seconds.

### Phase 2: The hard parts. Sat 15:00 to 23:00
| Task | Stream | Done when |
|---|---|---|
| Consent model, `assert_consent()`, withdraw, corrections, access log | A | Withdraw then read = 403, logged |
| Cases: assign, escalate, close; notifications; idempotency keys | A | Retry of same request does not duplicate |
| Name matcher + pair test set; dedupe | B | False-match rate measured; other "Muhammad Aslam" not matched |
| OCR + document consistency + edit-risk indicators; Jev document Nouls | B | Edited certificate flagged as risk |
| Rule versions, publish, Digital Twin simulate | B | v2 published live, old case shows v1 |
| SafeSwitch payout change with 48h hold job + confirmation | A + B | Helper cannot confirm; flagged account goes to officer |
| Offline outbox (Dexie), saved progress, sync | C | Offline claim syncs once on reconnect |
| Helper Mode: family list, fast switch, per-family consent | C | Switching never shows another family's data |
| Admin rule editor + Digital Twin screen; auditor trace view | C | Usable end to end |
| Urdu audio clips generated for all prompts and reason codes | D | Clips cached in PWA |

**Milestone M2 (Sat 23:00):** challenges 1-7 each have a working demo moment.

### Phase 3: Protection, evidence and polish. Sat 23:00 to Sun 03:30
| Task | Stream | Done when |
|---|---|---|
| Scam Shield: Jev Nouls + code checks + phone-pressure question + case cross-check | B | Fee scam flagged with reasons |
| Scam Map + analytics per tenant | C | Map shows counts by type / area / hour |
| Labelled eval sets: mock cases (~200), name pairs, scam messages from public examples | B | Sets committed with source notes |
| Eval runner + eval page: cost curve sweep, wrong approvals, FPR / FNR, UNSURE rate, latency, cost | B + C | Page renders live numbers |
| Judge console (admin-only): go offline, inject duplicate, publish v2, withdraw consent, upload forged cert, break a mock service, borderline scam | D | Every button works and is audited |
| Audit replay screen | C | Step through a case's events |
| Public API keys + webhooks + Swagger polish | A | External call with API key works in Swagger |

**Sleep Sun 03:30 to 08:00** (stagger if needed so one person is always awake to fix deploys).

### Phase 4: Feature freeze and hardening. Sun 08:00 to 13:00
| Task | Stream | Done when |
|---|---|---|
| **Feature freeze at 10:00.** Only fixes after this | all | - |
| `security-reviewer` + `code-reviewer` agents on all of `backend/` | A | No CRITICAL / HIGH left |
| Playwright E2E on the demo script; RBAC matrix; consent tests | D | All green in CI |
| Clean-device test on a real phone with throttled network | D | Golden path works |
| Monitoring: Sentry, logs, uptime alerts | A | Errors visible |

### Phase 5: Ship. Sun 13:00 to 17:30
| Task | Owner | Done when |
|---|---|---|
| Final deploy, seed reset, smoke test | Aiza | Deployed link stable |
| README: setup, architecture, real vs simulated, limits, prior work | both | README complete |
| Record demo video (also the backup for judging), upload to Drive (public link) | Teammate | Link works in incognito |
| Slides (optional) | Teammate | 8-10 slides |
| **Submit** | Aiza | Before 17:30 |

### Monday before judging
- Rehearse the demo 3 times with a timer.
- Ping the deployed link and reset seed data 30 minutes before.
- Have the backup video and a local run (`docker compose up`) ready in case venue internet fails.

## If something slips (order of protection)

We keep full scope. If a stream falls behind, protect the demo in this order, and keep the rest in progress:

1. Golden path (claim to decision to officer to payout) on the deployed link.
2. "I am not sure" + name variants + consent take-back + rule v2 (the challenges judges probe first).
3. Explanations (Urdu audio) + audit replay.
4. Scam Shield + eval page.
5. Offline sync, Helper Mode, SafeSwitch, Digital Twin.
6. Scam Map, analytics, webhooks.

## Working agreement

- Branch per task: `feat/<stream>-<thing>`. Pull request into `main`; the other person (or `code-reviewer` agent) reviews.
- Tests first for the decision engine, RBAC, consent, matching and audit (ECC `tdd-workflow`). UI can be tested by E2E.
- Every finished task: tick it in `docs/02-COMPLIANCE.md`, add a line to `docs/STATUS.md`.
- Never commit secrets. Never copy code from earlier projects.
- Blocked for more than 30 minutes: write it in STATUS.md and tell the other person.

## Definition of done (for any feature)

- Works on the deployed link, not only locally.
- Enforced on the server (not only hidden in the UI).
- Writes audit events.
- Has at least one test for the risky part.
- Shows up in the demo script or judge console.
