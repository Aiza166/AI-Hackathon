# Sahara: Survivor Pension Claims (Prototype)

> **PROTOTYPE ONLY. Not an official government service.**
> Every identity, family record, death record, pension and payment in this project is **simulated (mock)**. No real personal data is used anywhere.

Entry for **Coder's Cup 2026 AI Hackathon: "The Last Mile: AI on Public Rails"** (ACM, FAST-NUCES Karachi).
Build window: Fri 20 Nov 2026, 6:00 PM to Sun 22 Nov 2026, 6:00 PM PKT. Live judging: Mon 23 Nov.

## The one sentence

**We help widows claim their late husband's pension even though they can't read the forms, have a weak phone signal, their records spell names differently, and scammers and fake heirs target them.**

## What it does (short version)

1. A widow (or a community helper for her) starts a survivor pension claim by **voice and icons**, on a weak connection, with progress saved on the phone.
2. The platform checks the claim against **mock** identity, family, death, pension and payment services, where names are spelled in different ways.
3. A **decision engine** (versioned rules + Jev as a sensor + code-side routing) either auto-approves, asks for one specific extra proof, or says **"I am not sure"** and hands the case to an officer with notes. It never rejects anyone by itself.
4. Every decision has a **simple Urdu reason** for the citizen and a **full trace** for the auditor.
5. **SafeSwitch** protects the payout: changing the receiving account is held and needs the citizen's own confirmation.
6. **Scam Shield** checks forwarded "your pension is released, pay a fee" messages against the person's real case.
7. Citizens **see, share, withdraw and correct** who can access their data. Withdrawal blocks access at once and is logged.

## Docs (read in this order)

| # | Doc | What is in it |
|---|---|---|
| 1 | [docs/01-IDEA.md](docs/01-IDEA.md) | The idea, the story step by step, users and roles |
| 2 | [docs/02-COMPLIANCE.md](docs/02-COMPLIANCE.md) | Every requirement in the brief mapped to where we meet it |
| 3 | [docs/03-ARCHITECTURE.md](docs/03-ARCHITECTURE.md) | Stack, decision engine, data model, API, security |
| 4 | [docs/04-BUILD-PLAN.md](docs/04-BUILD-PLAN.md) | Team roles, hour-by-hour timeline, milestones, cut list |
| 5 | [docs/05-DEMO-SCRIPT.md](docs/05-DEMO-SCRIPT.md) | The live demo, judge console, backup plan, Q&A prep |
| - | [docs/SECURITY-CHECKLIST.md](docs/SECURITY-CHECKLIST.md) | Security audit against the GitHub Well-Architected and Invicti checklists, STRIDE threat model, scanner results |
| - | [docs/STATUS.md](docs/STATUS.md) | **Living status**: what is done, decisions, open questions |
| - | [PRIOR_WORK.md](PRIOR_WORK.md) | Disclosure of related prior work (pending organizer clearance) |
| - | [kissa.md](kissa.md) | Kissa's setup steps and task list |
| - | [CLAUDE.md](CLAUDE.md) | Rules and commands for Claude Code sessions (and humans) |

## Run it locally

```bash
docker compose up -d                      # Postgres + Redis
cd backend && python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt && copy .env.example .env
alembic upgrade head && python -m app.seed   # demo data, all PINs 1234
pytest && uvicorn app.main:app --reload   # API docs: http://localhost:8000/docs
cd ../frontend && npm install && npm run dev   # http://localhost:5173
```

## Team working rules

- All code in this repo is written **during the hackathon**. Never copy code, models, or data files from any earlier project (including our FYP).
- Mock everything. Never put real names, CNICs, phone numbers or photos in seed data.
- Never commit secrets. Use `.env` (ignored) and keep `.env.example` up to date.
- Small branches, pull request into `main`, conventional commit messages (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
- Update [docs/STATUS.md](docs/STATUS.md) when you finish something or hit a blocker.

## Real vs simulated

Filled in as we build. Final version goes in the submission README.

| Part | Real or simulated |
|---|---|
| Identity (NADRA-like), family records, death registry, pension office | Simulated (mock APIs with seeded fake data) |
| Payments (Raast-like) | Simulated |
| SMS / WhatsApp delivery | Simulated (in-app inbox) |
| Jev decision model | Real API calls (TypeSafe), pinned version |
| Urdu audio | Real: Azure neural TTS (`ur-PK-UzmaNeural`) when keys are set, else the phone's speech engine |
| Document reading (OCR) | Real: Azure Document Intelligence `prebuilt-read` when keys are set, else Tesseract in the container. The documents are mock specimens |
| Document checks (stamp copy-move, ELA, registry cross-check, Jev image questions) | Real code; indicators for an officer, never a verdict. The registry compared against is the mock one |
| Login, roles, consent, audit log, rules engine | Real (implemented in this project) |
| Scam Shield link checks (lookalike, shortener, punycode, IP, TLD, http) | Real code, deterministic, links never opened. Allowlist = mock `pension.gov.example` + real-world reference domains (gov.pk, bisp.gov.pk, ...) |
| Scam Shield caller checks | Real code. Official short codes (8171, 0800-26477) appear as real-world patterns, treated as evidence never proof; app data uses mock numbers |
| Screenshot check (OCR) | Real: Azure Document Intelligence / Tesseract on the uploaded screenshot. Not stored |
| Voice note / call recording check | Real: ffmpeg conversion + Azure speech-to-text (`ur-IN`) when keys are set, else "type what was said". Not stored |
| Share to Sahara from WhatsApp / SMS | Real PWA Web Share Target (installed app); stays on the phone until she taps Check |
| Second sensor (cascade) | Real Azure OpenAI chat model (gpt-4o-mini) when `SECOND_SENSOR_*` is set, called only when Jev is unsure; off without the settings |

Infrastructure (Railway services, Azure resources, variable names): [docs/INFRA.md](docs/INFRA.md).
