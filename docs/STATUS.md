# STATUS (living document)

> Update this whenever you finish something, decide something, or get blocked. Newest entries at the top of each section.

## Current phase

**Phase 1 done. Phase 2 in progress (consent done).** See [04-BUILD-PLAN.md](04-BUILD-PLAN.md).

### Live (Railway, project "charming-youth")

- **App:** https://confident-growth-production-1cfebeef.up.railway.app
- **API + Swagger:** https://ai-hackathon-production-31dd3038.up.railway.app/docs
- Auto-deploys on every push to `main` (backend from `/backend`, frontend from `/frontend`, both via Dockerfile). Postgres is a Railway service; the API migrates and seeds demo data on first boot.
- Railway trial: $5 credit / 30 days. "Limited trial" may restrict outbound network (Jev calls): link GitHub to the Railway account or add a card to lift it.
- `TYPESAFE_API_KEY` is set on Railway (copied from backend/.env via the Railway CLI, never printed). Whether the limited trial lets the API reach Jev is checked when Scam Shield ships.
- Railway CLI is linked in the repo folder: `npx @railway/cli status`, `npx @railway/cli logs --service AI-Hackathon`.

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
| Sat 21 Nov | Kissa | **Offline outbox** (`feat/c-offline-outbox`, Challenge 7): every claim step saved on the phone (Dexie/IndexedDB), reload resumes at the same step; "Send" stores the claim in an outbox with an idempotency key (`Idempotency-Key` header) and tries at once; no signal = "saved on this phone, waiting to send" strip with Send now + Listen; sends itself on reconnect. Dexie lazy-loaded in its own chunk (31 KB gzipped, not in the first screen); main JS 82.8 KB. Verified: reload mid-claim resumes; offline send queued; reconnect + "online" event + double "Send now" = exactly one `POST /cases` (201). **Ask (Aiza):** backend does not yet honour `Idempotency-Key` on `POST /cases`; today the 409 "already have an open claim" stops resends of the same claim. |
| Sat 21 Nov ~16:30 | Aiza + Claude | **Server duplicate protection for `POST /api/v1/cases`**. Optional `Idempotency-Key` header (IETF draft): table `idempotency_keys` (unique per principal + key, sha256 of the canonical body). Same key + same body after completion replays the stored response (same status and body, `meta.idempotent_replay=true`); same key + different body = 422; still in flight = 409; a failed request releases the key so a retry can proceed; an in-flight row older than 2 minutes can be taken over. Keys are per user. Also fixed: a second open claim with a blank deceased CNIC is now refused (409 with the existing reference) when the canonical deceased name matches (>= 95). 7 new tests in `test_idempotency.py`. Frontend outbox (PR #3) can now rely on the header. |
| 2026-11-21 (Sat) | Aiza + Claude | **Docs aligned with verified research** (01-IDEA, 02-COMPLIANCE, 03-ARCHITECTURE, 04-BUILD-PLAN, 05-DEMO-SCRIPT). Rule v1 = federal O.M. No. 1(13)-Reg.6/83 as updated 24-06-2024 (widow for life till remarriage, then children/daughters, no time cap); v2 = O.M. F.No. 9(3)R-6/2024-264 dated 10-09-2024 + clarifications 10-10-2024 and 22-01-2025 (widow unchanged; other heirs max 10 years; children 10 years or till 21, whichever later; disabled for life; only entitlements from 10-09-2024; existing pensioners exempt), with source URLs. Demo shows the Rakha heirs (2019) pinned to v1 and the Haider heirs (2024) capped under v2. Rules R1-R7 rewritten with bases; assumptions marked (children's clock start, n = 4 share split, single-pension rule). Fixes: no QR verification claim; "3 days" labelled a mock target; Scam Shield content outweighs sender ID (8171 spoofed, PID PR No. 59, 5 Jul 2024; BISP 8171 and 0800-26477 confirmed); missing EXIF never counts against the claimant; Jev image header + PNG/JPEG 280-1568 px + Box paired with a presence Noul; payout hold 48h, up to 4 business days on a red flag (UK FCA max); no name auto-match without exact CNIC. New "Judge Q&A risks" section in 05-DEMO-SCRIPT. Fixed: backend v1 and v2 rulesets now use federal son age 21 (was 25, Sindh text); test renamed to test_son_over_21; full suite passes. Sources (parent folder, outside the repo): `reports/Survivor pension research.md`, `research_notes/survivor-pension/verify_A_summary_sec1.md`, `verify_B_sec2.md`, `verify_C_sec3_4.md`, `verify_D_sec5_7.md`, `verify_E_rule_v2.md`. |
| 2026-11-21 (Sat) | Aiza + Claude | **Docs updated from Round 2 research** (01, 02, 03, 04): mock Raast title fetch returns a masked title + account type, never a CNIC, and no match verdict (our MATCH / CLOSE_MATCH / NO_MATCH layer is our design); 48h payout hold labelled our design (no Pakistani rule found); voice clips MP3 not Opus; removed the unsupported Google `ur-PK` STT claim; hosting now says Railway for API + PWA as deployed, Cloudflare Pages as fallback (Vercel Hobby is non-commercial only); scam report routes added (NCCIA 1799, PTA 0800-55055 / 9000 / 420, SBP Sunwai, BISP), 8557 and 9915 excluded. Mock CNICs keep the 90000 prefix per CLAUDE.md. Source (outside repo): `reports/Round 2 research.md`. |
| Sat 21 Nov ~05:30 | Aiza + Claude | **Frontend redesign**: design system + SVG pictograms; login shows phone + PIN with a hidden 'Demo accounts (mock)' toggle; citizen My data (who can see / who saw / fix a mistake); helper lock states; admin Rules + Digital Twin + publish; officer queue + trace panel; auditor filter + verify. Citizen JS 81 KB gzipped. Checked on localhost against the current API (My data, Digital Twin 2 of 4 changed). Not yet checked at phone width; Scam Shield and SafeSwitch screens not built yet. |
| Sat 21 Nov ~05:00 | Aiza + Claude | **Scam Shield + Scam Map (API, Challenge 8)**. Jev (pinned jev-1.14.0) answers 7 small questions about the message (fee, code, link, claims government, urgency, payment ready, instructions aimed at AI); code decides: content beats sender ID, case cross-check ("no payment waiting"), "someone on the phone" raises risk, unofficial links flagged. Jev down = keyword fallback that never says genuine. Stores only a text hash + signals; Scam Map by type/area/hour. API-key route for outside systems. Verified with real Jev: English + Roman Urdu fee scams = LIKELY_SCAM, genuine = LOOKS_GENUINE. /readyz now reports jev_reachable. 112 tests. |
| Sat 21 Nov ~04:30 | Kissa | **Phase 0 (C+D)**: repo access confirmed (push works), docs read, screen list + text sketches in `docs/screens/`. Local setup done: Docker Postgres + Redis up, backend venv (Python 3.12), migrations + seed, backend tests pass (83/83 at the time), frontend installs and builds, signed in as Zainab. |
| Sat 21 Nov ~04:30 | Aiza + Claude | **SafeSwitch (API)**: payout account change requests with Confirmation-of-Payee check, flags (payee close/no match, account used by another claim, change within 30 days of death), 48h hold or 4 business days when flagged, confirmation only by the claimant's own PIN (helpers can start but never confirm), officer approve/reject for flagged, apply after hold (scheduler or judge-console skip). All audited. 104 tests. Endpoints in kissa.md. |
| Sat 21 Nov ~04:00 | Aiza + Claude | **Rules that change + Digital Twin (API)**. Draft (validated), simulate (re-decides past cases under the draft, writes nothing), publish (old version retired; old decisions keep v1). Seed has 4 approved past cases: 2 heirs eligible after 10 Sep 2024 change under v2 (end 2034-11-01), 2 exempt (2019). Siblings in the FRC now count as lawful co-claimants. Deployed DB re-seeds once when SEED_VERSION changes. 96 tests. |
| Sat 21 Nov ~03:30 | Aiza + Claude | **Deployed to Railway**: backend (Dockerfile, migrate + seed on first boot, proxy headers) + Postgres + frontend (Vite build served by nginx). JWT secret generated by Railway (`${{secret(64)}}`), CORS limited to the frontend domain + localhost. Verified live: /healthz, /readyz (DB ok), demo login, CORS preflight, frontend loads with PROTOTYPE banner. |
| Sat 21 Nov ~02:45 | Aiza + Claude | **Phase 2: consent and take-back (API)**. `consents` + `correction_requests` tables; `assert_consent()` on every case read and on helper filing; withdraw/change fields/re-grant; "who saw my data" access log from the audit trail (DATA_ACCESS, CONSENT_DENIED); correction requests reviewed by officers. Withdrawal blocks the very next request (403, logged). Auditors keep read-only oversight (logged). Helper family list hides CNIC without consent. 90 tests. Frontend screens: Kissa (endpoints in kissa.md). |
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

None.

### Setup tips

- Port 5432 already taken (a native Postgres on your laptop): add a git-ignored `docker-compose.override.yml` mapping `5433:5432`, use port 5433 in `backend/.env`, and set `TEST_DATABASE_URL` to the 5433 `sahara_test` URL for pytest.
- Behind a proxy run `uvicorn app.main:app --proxy-headers --forwarded-allow-ips='*'` so rate limits see real client IPs.
