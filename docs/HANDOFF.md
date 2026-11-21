# Handoff: everything you need to know (Sat 21 Nov, evening)

Written for Kissa (and any Claude session helping her). It explains the whole project from the start in plain words, what is done, what is left, and how we work now. Read this first, then `kissa.md` section 0.

## 1. The project in one minute

**Sahara** is a prototype (everything is mock) that helps a widow claim her late husband's pension safely:

- She (or a community helper, with her consent) makes the claim on a cheap phone, in Urdu, with pictures and voice, even with weak signal.
- The system checks her identity, family and death records, and decides: **approve**, **ask for proof**, or **"I am not sure" -> a human officer**. It never rejects anyone by itself.
- It protects her money: **SafeSwitch** holds any change of her payout account and needs her own PIN.
- It protects her from scams: **Scam Shield** checks a suspicious SMS, WhatsApp message, link, screenshot or call and tells her "likely scam / not sure / looks genuine" with reasons, and how to report it.
- Every action is recorded in a tamper-evident audit log; she can see who looked at her data and take back consent.

Hackathon: Coder's Cup 2026, "The Last Mile: AI on Public Rails". Submit by **Sun 22 Nov 17:30**. Judging Mon 23 Nov: judges try the live app and try to break it. Rubric: AI 30, SaaS/architecture 20, real-world problem 15, accessibility 10, safety/privacy 15, innovation 10.

## 2. How we got here (short story)

1. **Fri night:** picked the idea, wrote the plan (`docs/01`-`05`), set up the repo, Railway hosting, and the ECC toolkit. Researched real Pakistani pension rules (`docs/research/`).
2. **Sat early morning:** built the backend (claims, decisions, name matching, rules v1/v2, Digital Twin, consent, audit chain, SafeSwitch API, Scam Shield API) and first screens; redesigned the UI; deployed live.
3. **Sat morning:** your PRs #1 (setup notes) and #3 (offline outbox) were reviewed, fixed and merged (see `kissa.md` for what changed in your code). The server now de-duplicates retried claims (Idempotency-Key).
4. **Sat day:**
   - #4 evaluation API + mock document images + matcher fix (a wrong date of birth never auto-approves).
   - #5 Scam Shield + SafeSwitch screens, date-of-birth step, mock bank account-holder check.
   - #6 document checks (Azure OCR, forensics that catch an edited death certificate, Jev image questions) + Azure Urdu voice.
   - #8 security hardening against two professional checklists (`docs/SECURITY-CHECKLIST.md`, 148 items).
   - #19 fixes for every bug the browser test found (rule v2 demo, offline reload, consent, demo fill).
   - #20 Scam Shield v2 built from Aiza's FYP knowledge (no FYP code): WhatsApp share, screenshots, link and call checks, and a **two-model cascade**: Jev (fast, cheap) on everything, gpt-5-mini (Azure) only on hard cases. Measured on our invented test set: 74% -> 84% accuracy, 0 false alarms.
5. **Sat evening:**
   - #21 monitoring: Sentry error tracking on backend and frontend (CNIC, IBAN, PIN, phone and tokens scrubbed before sending; admin `POST /api/v1/admin/sentry-test` shows a test error on the dashboard), Codecov coverage in CI (backend ~94% lines).
   - #22 **Evaluation page** (officer/admin/auditor tab: cost curve with 0.95 marked, wrong approvals, name-matching rates, Scam Shield and document cascade tiers with accuracy, speed, cost, model ids; every chart has a table view) and **Judge console** (admin tab: fault switches for each mock government service, simulated outages for Jev / gpt-5-mini / Azure OCR / Azure voice with safe fallbacks, live status, demo reset, sample messages and documents, live audit feed).

## 3. What is where

- Live app: https://confident-growth-production-1cfebeef.up.railway.app (API: https://ai-hackathon-production-31dd3038.up.railway.app). Test logins on **localhost** first (project rule); use the live site for the final phone check once Aiza says OK.
- Services and keys (names only): `docs/INFRA.md`. Keys live only in `backend/.env` (ask Aiza; never commit it) and on Railway.
- Rules for code: `CLAUDE.md`. Skills to use: `docs/SKILLS.md`.
- Progress log: `docs/STATUS.md`. Bugs and test results: `docs/TEST-REPORT.md`. Demo story: `docs/05-DEMO-SCRIPT.md`.
- Browser tests (Playwright): `frontend/e2e/` (own package; see its README).

## 4. How we work now

- **Branch per task, PR into `main`.** Conventional commit messages, no AI attribution lines.
- **Merging:** you may squash-merge **your own** PRs once CI is green (backend, frontend, security jobs). Ask Aiza first if the PR touches backend decision logic, security, or database migrations. Never force-push `main`.
- **Dependabot PRs (#9 to #18): leave them open. Do not merge, do not close.** They are big version jumps (Python 3.15, Node 26, bcrypt 5...) that could break the live site before judging. We revisit after Monday.
- `main` auto-deploys to Railway in about 3-5 minutes; check `/readyz` after a merge.
- When you finish something: tick it in `kissa.md`, add a line to `docs/STATUS.md`, message Aiza.

## 5. Your tasks (in order)

1. **Full test of the merged app (most important).** Nothing has been clicked through end to end in a browser since PRs #8, #19, #20, #21 and #22. Run the Playwright suite (`frontend/e2e`) against a local stack, then click the golden path on your real phone on the live site once Aiza says OK. Watch especially: audio (Listen), photo step, Scam Shield screenshot/record, offline queue, and anything blocked by the new strict CSP (browser console "Refused to ..."). Write results in `docs/TEST-REPORT.md` (new dated section); fix small bugs in a PR, report big ones to Aiza.
2. **One real-user test.** Ask a relative or neighbour (ideally an older woman) to try the claim flow on a phone for 10 minutes. Don't help unless she is stuck. Note what confused her (anonymous: no name or photo). Put 3-5 findings and one short quote in `docs/USER-TEST.md`, and fix the easy ones.
3. **Sindhi and Punjabi text.** About 40 fixed citizen strings (claim steps, reasons, Scam Shield verdicts). Add a language choice (Urdu default). Label them "machine-assisted translation, to be reviewed". Audio stays Urdu (Azure has no Pakistani Punjabi voice). Keep the size budget.
4. **Demo script = one story** (5-7 min): Zainab claims, a scam SMS arrives and Scam Shield catches it, someone tries to change her payout account and SafeSwitch protects her, the officer handles the "not sure" case. Digital Twin and evaluation page only if judges ask. Update `docs/05-DEMO-SCRIPT.md`.
5. **Q&A cheat-sheet** for both of us (`docs/QA-CHEATSHEET.md`): why 0.95, what happens when Jev or Azure is down, how the audit chain works, how consent works, what is real vs simulated, the prior-work (FYP) answer, the evaluation numbers and their limits. Then rehearse together on Sunday.
6. Then: phone-width polish, Urdu audio clips you still want offline, demo video (Drive link), slides if time.

**Aiza does:** messages the organizers about the prior-work (FYP) clearance and keeps the written reply; final README; merge freeze Sunday ~16:00.

## 6. Honest weak spots (so you're not surprised in Q&A)

- The claim decision is rules + fuzzy matching, not AI; the AI is in Scam Shield, document checks and voice.
- Evaluation sets are small and invented (80 messages, 20 documents, 200 claims); we say so on screen.
- Everything is mock; no real government system is connected.
- Voice input in Urdu is weak (Azure recognises Indian Urdu only); voice output is good.
- Demo PIN 1234 is public by design.
