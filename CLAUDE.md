# CLAUDE.md

Guidance for Claude Code (and humans) working in this repo. Read this first, then `docs/STATUS.md`.

## What this is

**Sahara**: a PROTOTYPE survivor pension claim platform for Coder's Cup 2026 AI Hackathon ("The Last Mile: AI on Public Rails", FAST-NUCES Karachi). A widow (or a community helper for her) claims her late husband's pension by voice and icons on a weak connection; the platform decides, explains and protects, and says "I am not sure" and hands the case to an officer when it should.

Build window ends **Sun 22 Nov 2026, 18:00 PKT** (submit by 17:30). Judging Mon 23 Nov: judges score **behaviour, not claims**, and will try to break it live.

## Hard rules (never break)

1. **Prototype, mock data only.** No real names, CNICs, phone numbers, photos or accounts anywhere (code, seeds, tests, screenshots). Mock CNICs start with `90000`, mock IBANs with `PK00MOCK`. Every page shows the PROTOTYPE banner.
2. **All code is written during the hackathon.** Never copy code, models or data files from any earlier project (including the team's FYP). See `PRIOR_WORK.md`.
3. **Never commit secrets.** Keys live in `backend/.env` (git-ignored). Keep `.env.example` updated with names only.
4. **Security is enforced on the server.** Role checks, consent checks and tenant isolation live in the API, never only in the UI. Every user, AI and system action writes an audit event.
5. **The system never rejects anyone by itself.** Only an officer can reject. Low confidence or any red flag routes to `UNSURE` (officer) with reason codes.
6. **Jev is a sensor, code decides.** Jev (`jev-1.14.0`, pinned) answers small factual yes/no questions; rules + thresholds in code decide. Never ask Jev "is this a scam / should we approve?". Noul > 0.7 = yes, < 0.3 = no, between = undecided (treat as unsure).
7. **Citizen-facing text is fixed, not generated.** Reasons come from `backend/app/decision/explanations.py` (Urdu + English + audio key + icon).
8. **Never say "fake" or "forged" on screen.** Document checks are "needs a second look" indicators for an officer.

## Layout

```
backend/   FastAPI (Python 3.12), SQLAlchemy 2, Alembic, Postgres
  app/api/        routers (auth, me, cases, audit, admin, public)
  app/core/       config, auth/RBAC, security, audit chain, rate limit, envelope
  app/decision/   matching, rules engine, rulesets/*.json, facts, engine, explanations, jev_client
  app/mock/       mock NADRA / FRC / death registry / pension office / Raast (+ fault injection)
  app/services/   case lifecycle
  app/seed.py     demo world (python -m app.seed)
  tests/          pytest against a separate sahara_test database
frontend/  React + Vite + TypeScript PWA (offline-first), plain CSS
  src/api/        fetch client + types (mirror backend/app/schemas)
  src/pages/      Login, ClaimWizard, CaseResult, CitizenHome, OfficerHome, AuditorHome
docs/      01-IDEA, 02-COMPLIANCE, 03-ARCHITECTURE, 04-BUILD-PLAN, 05-DEMO-SCRIPT, STATUS, research/
docs/team/   team task list, handoff, AI tooling notes
```

## Commands

```bash
docker compose up -d                                  # Postgres + Redis (repo root)
cd backend && .venv\Scripts\activate                  # Windows (python -m venv .venv first time)
pip install -r requirements.txt
alembic upgrade head && python -m app.seed            # demo data, all PINs 1234
pytest                                                # all backend tests must pass
uvicorn app.main:app --reload                         # http://localhost:8000/docs
cd frontend && npm install && npm run dev             # http://localhost:5173 (proxies /api to :8000)
npm run build                                         # must pass; check size budget
```

Tests need a `sahara_test` database once: `docker compose exec db psql -U sahara -c "CREATE DATABASE sahara_test"`.

Demo logins (PIN 1234): Zainab 00000000001, Rukhsana 00000000002, helper 00000000010, officer 00000000020, admin 00000000030, auditor 00000000040.

## Key design facts

- Routes: `AUTO_APPROVE` (confidence >= 0.95 and no red flag), `ASK_PROOF` (something specific missing, or 0.70-0.95), `UNSURE` (red flag, service outage, or < 0.70). 0.95 comes from a 20:1 cost ratio (wrong approval vs delay).
- Name matching never matches without an exact CNIC; "Muhammad" variants carry little weight.
- Rules are versioned JSON (`backend/app/decision/rulesets/`, stored in `rule_versions`). v1 live; v2 = federal 10-year cap for non-spouse heirs (10 Sep 2024), draft. Every decision stores its rule version.
- Audit log is append-only (DB trigger) and SHA-256 hash-chained; `/api/v1/audit/verify`.
- API responses use one envelope: `{success, data, error, meta}`.
- Frontend size budget: citizen shell <= 170 KB total, JS <= 100 KB gzipped; audio clips ~15 KB; photos compressed on the phone.
- Low-literacy first: one question per screen, big touch targets (>= 48px), icon + Urdu + audio on every step, voice only pre-fills fields the user confirms.

## How we work

- Branch per task (`feat/<stream>-<thing>`), pull request into `main`, conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`). No AI attribution lines in commits.
- Tests for risky logic (decisions, matching, RBAC, consent, audit). Run `pytest` and `npm run build` before pushing.
- Contract changes (`backend/app/schemas/*`, reason codes) affect the frontend: tell the other person.
- When you finish something or get blocked: add a line to `docs/STATUS.md`, tick `docs/02-COMPLIANCE.md`.
- Useful ECC tools (if installed): `/plan`, `tdd-workflow`, `/code-review`, agents `code-reviewer`, `security-reviewer`, `react-reviewer`, `a11y-architect`, `e2e-runner`.

## Skills

See [docs/team/AI-TOOLING.md](docs/team/AI-TOOLING.md) for which installed skills to use for each build step.
