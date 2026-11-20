# STATUS (living document)

> Update this whenever you finish something, decide something, or get blocked. Newest entries at the top of each section.

## Current phase

**Phase 0: Foundations** (Sat 21 Nov 00:30 to 03:00 PKT). See [04-BUILD-PLAN.md](04-BUILD-PLAN.md).

## Log

| When (PKT) | Who | What |
|---|---|---|
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
| Prior work (FYP) handled by light disclosure, pending organizer clearance | Safest option; no FYP code reused |

## Open questions

- [ ] Organizer reply on prior work (FYP) under "no pre-built projects".
- [ ] Jev: API key, rate limits, remaining credit; Urdu / Roman Urdu quality (smoke test).
- [ ] Exact eligibility rules and a realistic rule v1 to v2 change (deep research running).
- [ ] Azure speech key for pre-generated Urdu audio (or alternative).

## Blockers

None yet.
