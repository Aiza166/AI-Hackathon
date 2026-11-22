# Skills for the Sahara build

Every skill below is already installed on this machine: ECC skills live in `../.claude/skills/` (the hackathon folder), the rest come from user-level plugins. Nothing needs installing. Open Claude Code in `C:\Users\aizag\Desktop\ai hackathon` (the parent folder) so the ECC skills, rules and hooks load, then call a skill by name with the Skill tool or `/<name>`.

## Next steps and the skills to use

| Next step | Skills |
| --- | --- |
| Scam Shield + SafeSwitch screens | `frontend-skill`, `zizi-skills:i18n`, `design:accessibility-review` |
| Judge console + evaluation page (FPR/FNR, cost curve) | `dataviz`, `eval-harness` |
| Document upload + OCR + Jev document checks | `tdd-workflow`, `security-review` |
| Offline outbox + phone-width check | `browser-qa`, `e2e-testing` |
| README (real vs simulated) + demo video | `engineering:documentation`, `humanize-text`, `brag:brag` |

## By area

- **Planning:** `superpowers:brainstorming`, `superpowers:writing-plans`, `plan`, `plan-prd`, `superpowers:subagent-driven-development`, `superpowers:dispatching-parallel-agents`, `orch-add-feature`, `feature-dev`, `superpowers:executing-plans`.
- **Session handoff:** `save-session`, `resume-session`, `checkpoint`, `zizi-skills:status-update`, `update-docs` (keep `docs/STATUS.md` and `kissa.md` current).
- **Backend:** `tdd-workflow`, `superpowers:test-driven-development`, `fastapi-review`, `python-review`, `zizi-skills:database-optimization`, `error-handling`, `zizi-skills:security-and-hardening`, `security-review`, `security-scan`, `eval-harness`, `ai-regression-testing`.
- **Debugging:** `superpowers:systematic-debugging`, `build-fix`, `zizi-skills:debugging-and-error-recovery`.
- **Frontend:** `frontend-skill`, `frontend-design:frontend-design`, `zizi-skills:frontend`, `zizi-skills:design-guide`, `design:accessibility-review`, `design:ux-copy`, `zizi-skills:plain-language`, `zizi-skills:i18n`, `zizi-skills:information-architecture`, `dataviz`, `react-review`, `react-build`, `react-test`. Agents: `a11y-architect`, `performance-optimizer` (keep the shell under 170 KB).
- **Testing:** `e2e-testing`, `browser-qa`, `click-path-audit`, `verification-loop`, `superpowers:verification-before-completion`, `quality-gate`, `delivery-gate`, `test-coverage`, `run`. Agent: `e2e-runner`.
- **Deploy and ops:** `zizi-skills:infrastructure`, `engineering:deploy-checklist`, `zizi-skills:monitoring`, `production-audit`.
- **Review and git:** `code-review`, `review-pr`, `orch-review`, `santa-method`, `council`, `git-workflow`, `prp-commit`, `conventional-commit-review`, `pr`.
- **Docs and pitch:** `engineering:documentation`, `code-tour`, `architecture-decision-records`, `humanize-text`, `anthropic-skills:pptx` (optional slides), `brag:brag` (video draft; a real screen recording is still needed), `product-lens`, `zizi-skills:adversarial-review` (judge Q&A rehearsal).
- **Research:** `anthropic-skills:deep-research`, `zizi-skills:source-driven-development`, `zizi-skills:research-methods`.

## Do not use

Finance, SEO, marketing, Shopify, 3D/animation, ActiveCampaign, and other-language skills (Go, Rust, Kotlin, etc.). Canva/Figma only for mockups.

## Ground rules that still apply

- Never copy code from the FYP or any other repo.
- Cite sources for factual claims; mark unverified items.
- Test logins on localhost only, never on the live production-named site.
- Run backend tests with `backend/.venv/Scripts/python.exe -m pytest`.
