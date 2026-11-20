# STATUS (living document)

> Update this whenever you finish something, decide something, or get blocked. Newest entries at the top of each section.

## Current phase

**Phase 1 done (built overnight, Sat 21 Nov ~01:00-04:00 PKT). Next: Phase 2.** See [04-BUILD-PLAN.md](04-BUILD-PLAN.md).

### How to run it (2 terminals)

```bash
docker compose up -d                       # Postgres + Redis
cd backend && .venv\Scripts\activate
alembic upgrade head && python -m app.seed  # demo data, all PINs 1234
uvicorn app.main:app --reload               # http://localhost:8000/docs
cd frontend && npm run dev                  # http://localhost:5173 (proxies /api to :8000)
```

Demo logins (PIN 1234): Zainab 00000000001, Rukhsana 00000000002, helper Ayesha 00000000010, officer Kamran 00000000020, admin 00000000030, auditor 00000000040. The login screen has one-tap buttons for these.

## Log

| When (PKT) | Who | What |
|---|---|---|
| Sat 21 Nov | Kissa | **Phase 0 (C+D)**: repo access confirmed (push works), docs read, screen list + text sketches in `docs/screens/`. Frontend installs and builds (73.6 KB gzipped JS). Backend venv (Python 3.12) + deps installed; DB steps blocked on Docker Desktop (not yet installed on Kissa's laptop). |
| Sat 21 Nov ~04:00 | Claude (overnight) | **Security review** (independent agent, 13 findings) fixed: API keys can't list cases; tenant-scoped audit log; app refuses weak JWT_SECRET; auditors read-only; demo reset/faults only for platform admin; audit TRUNCATE hatch only in *_test DB; claim rate limit + duplicate-claim 409 + bounded recheck; PIN lockout (5 tries/15 min); row locks on officer actions; case refs from a sequence; citizens can't see officer IDs or others' case refs. 83 tests. Not fixed (known limits): refresh tokens not revocable; mock registry lookups not purpose-bound to a case; app DB user owns the audit table (production should use a separate non-owner role). |
| Sat 21 Nov ~03:00 | Claude (overnight) | **Phase 1 frontend**: login + demo personas, citizen/helper claim wizard (icons, Urdu, audio), decision result screen, Helper Mode family picker (40 families), officer queue with trace + approve/reject, auditor log + verify chain. 74 KB gzipped JS. Verified live: claim through the UI proxy auto-approves Zainab. |
| Sat 21 Nov ~02:30 | Claude (overnight) | **Phase 1 backend**: Postgres schema + migrations; append-only hash-chained audit log (DB trigger); JWT login, roles, API keys with scopes; mock NADRA/FRC/death registry/pension/Raast services with fault injection; name matching (no match without exact CNIC); rules as versioned JSON (v1 live, v2 = 10-year cap as draft); decision engine (AUTO / ASK_PROOF / UNSURE, never auto-reject, payee check, competing claims recheck); case APIs, officer queue, citizen explanation, auditor trace; seed data with messy names and traps. |
| Sat 21 Nov 02:30 | Aiza + Claude | Jev smoke test: GO. 20/20 invented messages (English, Roman Urdu, Urdu script) separated, 0 undecided, median 290 ms, model jev-1.14.0. Small hand-written set: a go/no-go signal, not an accuracy claim. Results in backend/results/jev_smoke.json |
| Sat 21 Nov 02:15 | Aiza + Claude | Survivor pension research done and applied: real 7-rule ruleset, rule v2 = federal 10-year cap (10 Sep 2024) replacing the unsourced remarriage idea, Confirmation-of-Payee check + 4-business-day hold on red flags, CNIC-required name matching, document checks as indicators only, Jev image limits, 170 KB budget. Reports in docs/research/ |
| Sat 21 Nov 01:30 | Aiza + Claude | Phase 0 scaffold: FastAPI backend (envelope, config, contracts, reason codes + Urdu text, Jev client pinned to jev-1.14.0, Alembic, 15 tests passing), Vite React PWA with PROTOTYPE banner, docker-compose (Postgres + Redis), CI, Jev smoke-test script, kissa.md |
| Sat 21 Nov 00:30 | Aiza + Claude | Plan docs written: idea, compliance checklist, architecture, build plan, demo script |
| Fri 20 Nov evening | Aiza + Claude | Read brief, installed ECC tooling locally, researched Jev and win strategy, chose the task |

## Decisions

| Decision | Why |
|---|---|
| Task: survivor pension claim, with SafeSwitch payout and Scam Shield | Serves all 3 personas; real approve/reject with high cost of a wrong approval; all 8 challenges arise naturally |
| Full scope (3-4 person plan), 4 streams, 2 people each running Claude Code agents | Team decision |
| Jev (`jev-1.14.0`, pinned) is a sensor; code + versioned rules decide | Jev has no "abstain" answer and reads adversarial text at face value; "I am not sure" must be a code route |
| Thresholds: auto-approve >= 0.95, human < 0.70, never auto-reject | Cost ratio 20:1 (wrong approval vs delay) |
| Stack: FastAPI + Postgres/Alembic + GoRules ZEN + React Vite PWA (Dexie) + Railway/Vercel | Python for AI pieces; always-on hosting avoids cold starts |
| Rule v2 = 10-year cap for non-spouse heirs (10 Sep 2024), not "remarried widows" | Only change with a primary source; has a grandfather clause for the Digital Twin |
| No auto name-match without exact CNIC; document checks are indicators, never "fake" | Research: "Muhammad" carries little evidence; forensics on phone photos is weak |
| Own small JSON rules engine instead of GoRules ZEN | Same idea (rules are versioned data, no redeploy), but simpler to author, test and show to judges; no heavy editor in the 170 KB budget |
| Jev not used for claim facts yet (model_id null) | Claim facts come from registries; Jev comes in for document images and Scam Shield in Phase 2-3 |
| Prior work (FYP) handled by light disclosure, pending organizer clearance | Safest option; no FYP code reused |

## Open questions

- [x] Jev API key obtained.
- [x] Jev smoke test: GO for English, Roman Urdu and Urdu script.
- [x] Jev credit: $4.75 available (plenty at ~$0.00002 per message).
- [ ] Jev rate limits (check console).
- [ ] Organizers' reply on prior work (asked on WhatsApp).
- [x] Eligibility rules and a real rule v1 to v2 change (10-year cap) from research.
- [ ] Azure speech key for pre-generated Urdu audio (or alternative).

## Next (Phase 2, Sat ~09:00)

- Aiza (A+B): consent model + `assert_consent()` + withdraw/correct; publish rule v2 + Digital Twin API; SafeSwitch payout change + 48h/4-day hold; documents upload + OCR + Jev document checks; idempotency keys; deploy to Railway.
- Kissa (C+D): offline outbox (Dexie), consent screens, admin rule editor + Digital Twin screen, Urdu audio clips, real pictograms, Vercel deploy. See [kissa.md](../kissa.md).

## Blockers

- Kissa: Docker Desktop (and WSL) not installed yet, so local Postgres/Redis, `pytest` and the signed-in frontend wait on that install.

Deploy note: behind a proxy run `uvicorn app.main:app --proxy-headers --forwarded-allow-ips='*'` so rate limits see real client IPs.
