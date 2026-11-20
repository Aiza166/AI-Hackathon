# STATUS (living document)

> Update this whenever you finish something, decide something, or get blocked. Newest entries at the top of each section.

## Current phase

**Phase 0: Foundations** (Sat 21 Nov 00:30 to 03:00 PKT). See [04-BUILD-PLAN.md](04-BUILD-PLAN.md).

## Log

| When (PKT) | Who | What |
|---|---|---|
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
| Prior work (FYP) handled by light disclosure, pending organizer clearance | Safest option; no FYP code reused |

## Open questions

- [x] Jev API key obtained.
- [ ] Jev: rate limits and remaining credit (check console); run `python -m scripts.jev_smoke` for Urdu / Roman Urdu go/no-go.
- [ ] Organizers' reply on prior work (asked on WhatsApp).
- [x] Eligibility rules and a real rule v1 to v2 change (10-year cap) from research.
- [ ] Azure speech key for pre-generated Urdu audio (or alternative).

## Blockers

None yet.
