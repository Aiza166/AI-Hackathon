# Kissa: start here

> Your personal task list. Aiza (and Claude) keep this updated. Tick boxes as you finish and push.
> Last updated: Sat 21 Nov 02:15, Phase 0 (research applied).

## 1. What we are building (2 minute read)

**Sahara**: a prototype platform that helps widows claim their late husband's pension safely, even when they can't read, have weak signal, records spell names differently, and scammers or fake heirs target them.

Read in this order: [README](README.md), then [docs/01-IDEA.md](docs/01-IDEA.md) (the story), then [docs/05-DEMO-SCRIPT.md](docs/05-DEMO-SCRIPT.md) (what judges will see). Skim [docs/04-BUILD-PLAN.md](docs/04-BUILD-PLAN.md) for the timeline.

## 2. Your streams

You own **Stream C (Frontend PWA)** and **Stream D (Demo & quality)**. Aiza owns A (platform/security) and B (decision engine/AI). Shout if you'd rather swap.

## 3. Setup (about 20 minutes)

1. Clone: `git clone https://github.com/Aiza166/AI-Hackathon.git` and open it.
2. Install: Node 20+, Python 3.12, Docker Desktop, Git.
3. Frontend:
   ```bash
   cd frontend
   npm install
   npm run dev        # http://localhost:5173
   ```
4. Backend (optional for you at first):
   ```bash
   docker compose up -d                 # Postgres + Redis, from repo root
   cd backend
   python -m venv .venv
   .venv\Scripts\activate               # Windows
   pip install -r requirements.txt
   copy .env.example .env               # ask Aiza for any keys; never commit .env
   pytest
   uvicorn app.main:app --reload        # http://localhost:8000/docs
   ```
5. Claude Code + ECC (the toolkit we use): clone `https://github.com/affaan-m/ECC` **outside** this repo, then from the folder that contains `AI-Hackathon` run:
   `node ECC/scripts/install-apply.js --target claude-project --profile core --enable-hooks`
   Then open Claude Code in that folder. Useful: `/plan`, `tdd-workflow`, `/code-review`, agents `react-reviewer`, `a11y-architect`, `e2e-runner`.

## 4. Your tasks now

### Phase 0 (tonight / first thing)
- [ ] Do the setup above; run the frontend; push one small commit (e.g., your name in this file) so we know access works.
- [ ] Read the 3 docs above.
- [ ] Draft the screen list and a rough sketch (a paper photo is fine) for: citizen home, claim steps, decision result, officer queue. Put it in `docs/screens/`.

### Phase 1 (Sat 09:00 to 15:00): golden path UI
- [ ] Set up routing (React Router) and a simple role login screen (phone + PIN).
- [ ] Generate API types from the backend: `npx openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.ts`. Until endpoints exist, use mock data (MSW) shaped like `backend/app/schemas/contracts.py`.
- [ ] Citizen claim flow: big icons, one question per screen, audio button on each screen (audio files come later; use the `audio_key` names from `backend/app/decision/explanations.py`).
- [ ] Decision result screen: icon + Urdu text + English text + play audio, from the `Explanation` contract.
- [ ] Officer queue: list sorted by priority and confidence; case detail; approve / reject with reason.
- [ ] Deploy the frontend to Vercel (Stream D) and send the link in the group.

### Phase 2 (Sat 15:00 to 23:00)
- [ ] Offline outbox with Dexie: save each claim step locally; queue actions with an idempotency key; "send now" button; sync on reconnect.
- [ ] Helper Mode: family list, fast switch, clear "now acting for: X" header, only families with consent.
- [ ] Consent screen: who can see my data, toggle fields, withdraw, request correction, "who saw my data".
- [ ] Admin rule editor screen + Digital Twin results table.
- [ ] Auditor: decision trace view.
- [ ] Urdu audio clips for every prompt and reason code (Stream D), cached by the PWA.

### Phase 3 (Sat 23:00 to Sun 03:30)
- [ ] Scam Shield screen (paste/forward message, verdict, reasons, "is someone on the phone with you?" question).
- [ ] Scam Map + analytics dashboard.
- [ ] Eval page (cost curve chart, false alarms, wrong approvals).
- [ ] Judge console page (buttons listed in docs/05-DEMO-SCRIPT.md).
- [ ] Audit replay screen.

### Phase 4-5 (Sunday)
- [ ] Playwright E2E for the demo script.
- [ ] Test on a real phone with a throttled network.
- [ ] Record the demo video, upload to Google Drive (public link).
- [ ] Slides (optional).

## 5. Design facts from research (keep these in the UI)

- Size budget: citizen app shell <= 170 KB total (JS <= 100 KB), each extra screen <= 30 KB, audio clips ~15 KB, photos compressed on the phone to ~200 KB. Check with `npm run build`.
- Never write "fake" or "forged" on screen: document checks say "needs a second look", each with its reason and "what this cannot tell".
- Payout screens show the payee check as **match / close match / no match**.
- Payout confirmation goes to the widow herself, never to the helper's phone.
- Rule v2 in the demo is the **10-year cap for non-spouse heirs (10 Sep 2024)**, not "remarried widows".
- Voice only pre-fills a field; the user always confirms with a tap.
- Full details: [docs/research/survivor-pension.md](docs/research/survivor-pension.md) and the last section of [docs/03-ARCHITECTURE.md](docs/03-ARCHITECTURE.md).

## 6. Rules (important)

- Everything is **mock**: no real names, CNICs, phone numbers or photos anywhere.
- Every page shows the **PROTOTYPE** banner (the component already exists: `src/components/PrototypeBanner.tsx`).
- Never commit `.env` or keys.
- Work on a branch (`feat/c-officer-queue`) and open a pull request into `main`.
- When you finish or get stuck: add a line to [docs/STATUS.md](docs/STATUS.md) and message Aiza.
- Low-literacy first: big touch targets, icons + audio, one decision per screen, works on a cheap phone.
