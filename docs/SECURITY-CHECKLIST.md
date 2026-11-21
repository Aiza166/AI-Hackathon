# Security checklist (Sahara prototype)

Sahara has been audited against two public application-security checklists. Each item that applies is one row below. The application controls the brief asked for are listed first, then the two checklists item by item.

- **GH**: GitHub Well-Architected, *Checklist for Application Security*: https://learn.github.com/well-architected/application-security/checklist (source: https://github.com/github/github-well-architected/blob/main/content/library/application-security/checklist.md)
- **INV**: Invicti, *Application security checklist: essential steps for secure development*: https://www.invicti.com/blog/web-security/application-security-checklist-essential-steps-for-secure-development

Status values:
- **done**: already in place before this audit.
- **fixed now**: changed in PR `feat/security-hardening`, with tests in `backend/tests/test_security_hardening.py`.
- **N/A**: does not apply, with the reason.
- **known limit**: accepted for a hackathon prototype, with the reason.
- **handed to scam agent**: the fix belongs in Scam Shield files that another stream owns.

Audited on 22 Nov 2026 by a manual review, an independent `security-reviewer` agent pass (16 findings, all handled below), AgentShield, pip-audit, npm audit, Bandit and gitleaks. Line numbers refer to the merge commit of this PR.

## Summary

148 rows across the three tables below. A row with a combined status (for example "done / fixed now") is counted under its first status.

| Status | Rows |
|---|---|
| done | 61 |
| fixed now | 39 |
| N/A | 26 |
| known limit | 19 |
| handed to scam agent | 3 |

Scanner results at merge time:
- **pip-audit** found 16 advisories in starlette 0.46.2 (multipart DoS, Range-header DoS, Host and path validation, form limits) and 1 in pytest 8.4.2. Fixed by moving to FastAPI 0.165 / starlette >= 1.3.1 and pytest 9. 0 remain.
- **npm audit**: 0 high, 0 critical. 4 moderate advisories in the build-time dependency `minimatch` (pulled in through `vite-plugin-pwa`). The only fix offered is a breaking downgrade of the plugin, so they stay a known limit.
- **Bandit** (`-ll -ii`): 0 high and 0 medium findings. Without the filter it reports 6 low findings, all false positives: `"bearer"` read as a password, an XML `escape` used for SSML output rather than parsing, `random` used to build synthetic evaluation data, and two other strings mistaken for passwords (`'muhammad'` in the name matcher, and a score threshold in `scam.py`).
- **gitleaks** v8.21.2 scanned all 44 commits on all branches: no leaks.
- **AgentShield**: grade B (80/100). All 11 findings are "missing prompt defense" items in `CLAUDE.md`, which is a developer guide and not a runtime prompt (low runtime confidence). The prompts that actually run are the Jev questions in the Scam Shield files (see the row handed to the scam agent).

## Threat model (STRIDE)

Assets: a claimant's identity (CNIC, DOB), her family record, the payout account (IBAN), the claim decision, the audit trail, and Azure and Jev credentials. The actors are citizens, helpers, officers, admins and auditors (one department each), outside systems with API keys, and anonymous internet users, including judges trying to break the demo.

| Threat | Example against Sahara | Controls | Residual |
|---|---|---|---|
| **S**poofing | Guess a widow's PIN; replay a stolen refresh token; forge a JWT | PIN lockout (5 in 15 min) at login and on the SafeSwitch step-up; bcrypt; HS256 pinned with iss/aud/typ/exp/sid/jti required; rotating single-use refresh tokens, where reusing one revokes the session; sign-out revokes the session | 4-digit PINs; one shared HS256 secret; no MFA (prototype) |
| **T**ampering | Edit an audit row; change someone else's payout account; upload an edited document | Append-only DB trigger and SHA-256 hash chain (`/audit/verify`); payout confirm only by the claimant's own PIN, with a hold and officer review when flagged; document forensics feed "needs a second look" indicators | The DB owner could disable the trigger (known limit, DB least privilege) |
| **R**epudiation | "I never approved that" | Every user, AI and system action audited with actor, role and tenant; sign-in sessions audited (LOGIN, TOKEN_REFRESHED, LOGOUT, REFRESH_TOKEN_REUSED) | Head hash not anchored outside the DB |
| **I**nformation disclosure | IDOR on `/cases/{id}`; a helper probing CNICs; CNICs in logs; caching of PII | Server-side role, tenant and consent check on every read, also on list endpoints; uniform 403/404; CNIC/IBAN masked in audit and logs; SQL parameters hidden in logs; `Cache-Control: no-store`; strict CSP | Mock registry lookups (admin/auditor) are not bound to a case purpose |
| **D**enial of service | Multi-GB body, decompression-bomb PNG, OCR on a huge image, IP rotation to beat rate limits | 9 MB body cap before parsing; 8 MB per photo; pixel cap checked before decode; Tesseract and Azure timeouts; slowapi on every route, keyed on the rightmost X-Forwarded-For hop | In-memory rate-limit store per process (no Redis) |
| **E**levation of privilege | A helper confirms a payout; an admin closes a pending case (an effective rejection); a citizen acts as an officer | `require_roles` on every route; the helper never reaches the PIN confirm; only an officer can reject or close a pending case; auditors are read-only | Demo admin PIN is public (known limit) |

## Application controls requested in the brief

| # | Item | Status | Evidence |
|---|---|---|---|
| A1 | Input validation at the boundary (Pydantic schemas with length, pattern and enum limits) | done | `backend/app/schemas/claims.py`; `ChangeIn` pattern in `backend/app/api/payout.py:26`; `LoginIn` in `backend/app/api/auth.py:26` |
| A2 | Audit filter `action` query bounded (it went into the audit chain unbounded) | fixed now | `backend/app/api/audit.py:28` |
| A3 | Output encoding: React escapes by default; no `dangerouslySetInnerHTML`, `innerHTML` or `eval` in `frontend/src` | done | grep of `frontend/src` (no hits) |
| A4 | Citizen-facing text is fixed, not generated (no reflected model output) | done | `backend/app/decision/explanations.py` |
| A5 | Validation errors never echo submitted values | done | `backend/app/core/envelope.py:26` |
| A6 | SSML for Azure TTS is XML-escaped | done | `backend/app/api/speech.py:99` |
| A7 | PIN lockout: 5 wrong PINs in 15 min; unknown phones still cost one bcrypt check, so timing does not reveal which phones exist | done | `backend/app/core/lockout.py`, `backend/app/api/auth.py` (`_DUMMY_HASH`); test `test_login_rate_limit_returns_429` |
| A8 | The SafeSwitch PIN step-up had no lockout (a stolen access token could guess the PIN). Now 5 wrong step-up PINs in 15 min lock it. Login failures are deliberately not counted, so a stranger who knows her phone number cannot lock her payout confirmation | fixed now | `backend/app/api/payout.py`, `backend/app/core/lockout.py`; tests `test_payout_pin_step_up_locks_after_5_wrong_pins`, `test_wrong_login_pins_do_not_lock_the_payout_step_up` |
| A9 | JWT: algorithm pinned, `iss`, `aud`, `exp`, `iat`, `typ` verified; now also `sid` and `jti` required | done / fixed now | `backend/app/core/security.py:52-55`; test `test_token_without_session_is_refused` |
| A10 | Access token lifetime 30 min, refresh 2 days | done | `backend/app/core/config.py` (`jwt_access_minutes`), `backend/app/core/security.py` (`REFRESH_TOKEN_DAYS`) |
| A11 | Refresh tokens could not be revoked: now a sessions table, rotation on every refresh, reuse detection revokes the whole session, sign-out revokes it, and access tokens carry `sid`, so they die at sign-out | fixed now | `backend/app/models/session.py`, migration `f3a9c1e2b4d6`, `backend/app/api/auth.py` (`refresh`, `logout`), `backend/app/core/auth.py` (`_from_jwt`); the PWA calls it on sign-out (`frontend/src/App.tsx:80`); tests `test_reusing_a_refresh_token_ends_the_whole_session`, `test_logout_revokes_refresh_and_access_tokens` |
| A12 | Weak or placeholder `JWT_SECRET` refused at startup | done | `backend/app/core/config.py:70` |
| A13 | AuthZ by role on the server, every route; denied attempts audited | done | `backend/app/core/auth.py:78`, `:91` |
| A14 | Consent checked on every single-record read (never cached) | done | `backend/app/core/consent.py:68`, `backend/app/api/cases.py:25` |
| A15 | Consent was not applied to list endpoints (`GET /cases`, `/queue`, officer `GET /payout-changes`) | fixed now | `backend/app/api/cases.py:125`, `backend/app/core/consent.py:38`, `backend/app/api/payout.py` (`officer_list`); test `test_withdrawn_consent_hides_cases_from_list_endpoints` |
| A16 | Tenant isolation: staff see only their department (cases, queue, audit, replay, payout changes) | done | `backend/app/services/cases.py:65`, `backend/app/api/audit.py` |
| A17 | IDOR on `/cases/{id}` and sub-routes (explanation, decisions, approve/reject/assign/escalate/close) | done | `_load` in `backend/app/api/cases.py:25`; test `test_other_citizen_cannot_reach_any_route_of_a_case` |
| A18 | IDOR on `/cases/{id}/documents/{doc_id}`: the document was looked up before case access (existence oracle) | fixed now | `backend/app/api/documents.py:59`; tests `test_document_id_of_a_hidden_case_does_not_leak_existence`, `test_document_of_another_case_is_not_found_through_my_case` |
| A19 | IDOR on `/payout-changes/{id}/confirm`, `/cancel` (claimant or starting helper only) | done | `backend/app/services/payout.py` (`confirm`, `cancel`); test `test_payout_change_ids_are_guarded` |
| A20 | Officer review of a payout change from another department answered 409 (leaked existence) | fixed now | `backend/app/services/payout.py:128` |
| A21 | `/speech/tts`, `/speech/stt` require sign-in (no resource ids) | done | `backend/app/api/speech.py` (`require_roles(*ALL_ROLES)`); test `test_speech_and_unknown_ids_need_auth_and_return_404` |
| A22 | Helper filing could probe whether a CNIC exists (two different 403 messages) | fixed now | `backend/app/api/cases.py:98`; test `test_helper_cannot_probe_whether_a_cnic_exists` |
| A23 | An admin could close a pending or approved case (an effective rejection or reversal by a non-officer; hard rule 5) | fixed now | `backend/app/services/cases.py:237`; tests `test_case_close_cannot_overturn_a_decision`, `test_only_an_officer_can_close_a_case_waiting_for_a_decision` |
| A24 | Audit replay was not itself audited | fixed now | `backend/app/api/audit.py:55` |
| A25 | Rate limiting on all endpoints (default 300/min, tighter limits on login, claims, uploads, payout, speech) | done | `backend/app/core/ratelimit.py:14`; test `test_default_limit_covers_routes_without_their_own` |
| A26 | Rate limits could be bypassed with a spoofed `X-Forwarded-For` (uvicorn trusts the leftmost entry): now keyed on the rightmost hop | fixed now | `backend/app/core/ratelimit.py:17`, `backend/start.sh:8`; tests `test_spoofed_forwarded_for_does_not_reset_the_limit`, `test_client_ip_uses_rightmost_hop` |
| A27 | Upload type checked by magic bytes, not only the declared type or extension | fixed now | `backend/app/documents/imaging.py:25`, `backend/app/api/documents.py` (`_read_limited`); test `test_upload_rejects_wrong_magic_bytes_even_with_image_type` |
| A28 | STT audio checked by magic bytes (RIFF/WAVE, OggS) | fixed now | `backend/app/api/speech.py:38`; test `test_stt_rejects_audio_whose_bytes_do_not_match_the_type` |
| A29 | Upload size: 8 MB per photo, about 1 MB per audio clip | done | `backend/app/api/documents.py:31`, `backend/app/api/speech.py` (`MAX_STT_BYTES`); test `test_upload_over_8_mb_is_refused` |
| A30 | Decompression bomb: `Image.MAX_IMAGE_PIXELS` set at import, and the pixel count checked before decode (Pillow only warns between 1x and 2x its limit) | fixed now | `backend/app/documents/imaging.py:20`, `:101`; tests `test_decompression_bomb_is_refused`, `test_pillow_pixel_limit_is_set_at_import` |
| A31 | EXIF stripped on storage (the stored copy is a fresh baseline JPEG with no exif, xmp or GPS) | done (verified now) | `backend/app/documents/imaging.py:146`; test `test_stored_copy_has_no_exif` |
| A32 | No path traversal: uploads are stored as bytes in Postgres, the client file name is never used, and the TTS disk cache file name is a sha256 hex | done | `backend/app/models/document.py`, `backend/app/api/speech.py` (`cache_key`) |
| A33 | Security headers on FastAPI: CSP `default-src 'none'; frame-ancestors 'none'`, HSTS, nosniff, `X-Frame-Options`, `Referrer-Policy: no-referrer`, Permissions-Policy (camera/mic off on the API), COOP, `Cache-Control: no-store`; Swagger gets its own CSP | fixed now | `backend/app/core/middleware.py:12`, `:21`; tests `test_api_responses_carry_security_headers`, `test_error_responses_also_carry_headers`, `test_swagger_docs_get_a_csp_that_lets_them_load` |
| A34 | Security headers on nginx (PWA): before this fix nginx dropped them on `/`, `/index.html`, `/sw.js` and `/assets` (a location-level `add_header` overrides server-level ones). Now one included file sets CSP (connect-src self + API origin, frame-ancestors none), HSTS, nosniff, DENY, Referrer-Policy, Permissions-Policy `camera=(self), microphone=(self)`, COOP; `server_tokens off` | fixed now | `frontend/security-headers.inc.template:4`, `frontend/nginx.conf.template:7`, `:12`, `frontend/Dockerfile` (`API_ORIGIN`); checked with `docker build` + `curl -I` on `/`, `/index.html`, `/sw.js`, `/assets/`, an SPA route |
| A35 | CORS: explicit origin list from the environment, no wildcard; `allow_credentials` was true without need | fixed now | `backend/app/main.py:40-41`; test `test_cors_does_not_allow_credentials` |
| A36 | Cookies and storage: no auth cookies; the access token lives in `sessionStorage` (gone when the tab closes on a shared phone); drafts in IndexedDB are wiped at sign-out | done | `frontend/src/api/client.ts:2`, `frontend/src/App.tsx` (`clearOwnerData`) |
| A37 | CSRF: bearer token in the `Authorization` header and no cookies, so a cross-site request carries no credentials. CSRF tokens are not needed | N/A | `backend/app/core/auth.py` (`HTTPBearer`) |
| A38 | Secrets: only in env vars (`backend/.env` git-ignored, Railway variables); `.env.example` has names only; gitleaks clean on the full history | done | `.gitignore:2`, `backend/.env.example`, gitleaks run above |
| A39 | Secret scanning in CI (gitleaks) | fixed now | `.github/workflows/ci.yml:84` |
| A40 | Dependency scanning: Dependabot (pip, npm, actions, docker) + CI `pip-audit` and `npm audit --audit-level=high` | fixed now | `.github/dependabot.yml`, `.github/workflows/ci.yml:75` |
| A41 | Known-vulnerable starlette 0.46.2 / pytest 8 upgraded | fixed now | `backend/requirements.txt:1-2` |
| A42 | SAST: Bandit in CI (CodeQL needs GitHub Advanced Security on a private repo) | fixed now | `.github/workflows/ci.yml:80` |
| A43 | Logging without PII: CNIC and IBAN masked in audit `resource` and `details`, including free-text reasons and notes and denied request paths | fixed now | `backend/app/core/audit.py:68`, `backend/app/core/redact.py`; tests `test_cnic_and_iban_in_free_text_are_masked_in_the_audit_trail`, `test_denied_path_with_a_cnic_is_masked` |
| A44 | Log lines masked on every handler (root and uvicorn), covering child loggers, %-args and traceback text. This matters for uvicorn access lines, because mock registry paths carry a CNIC | fixed now | `backend/app/core/redact.py` (`RedactingFilter`, `install_log_redaction`); test `test_access_log_lines_are_redacted` |
| A45 | SQL errors in logs carry no bound values; the Azure OCR warning logs only the exception type | fixed now | `backend/app/db.py:15`, `backend/app/documents/ocr.py` |
| A46 | PINs never logged or stored in plain text (bcrypt); API keys stored as sha256, shown once | done | `backend/app/core/security.py:68` |
| A47 | Error messages do not leak internals (generic 500, details only in server logs) | done | `backend/app/core/envelope.py:32` |
| A48 | SSRF: outbound calls only to fixed hosts (Jev `typesafe_base_url`, Azure `{region}.tts/stt.speech.microsoft.com`, the Document Intelligence endpoint from config); no user-supplied URL is ever fetched | done | `backend/app/core/config.py:27`, `backend/app/api/speech.py:104`, `backend/app/documents/ocr.py` |
| A49 | SQL injection: ORM only; the only `text()` calls are constants (`SELECT 1`, `nextval`, advisory lock with a bound parameter, TRUNCATE over a constant table list) | done | `backend/app/main.py` (`readyz`), `backend/app/services/cases.py:95`, `backend/app/core/audit.py`, `backend/app/seed.py:139` |
| A50 | DoS: request body capped at 9 MB before parsing (Content-Length and streamed chunks); the 413 carries the CORS and security headers | fixed now | `backend/app/core/middleware.py:10`, middleware order in `backend/app/main.py`; tests `test_oversized_body_is_refused_before_parsing`, `test_chunked_body_over_the_cap_is_refused` |
| A51 | DoS: OCR timeouts (Azure 20 s; Tesseract had none and now has 20 s), Jev 2 s / 8 s for images | fixed now | `backend/app/documents/ocr.py:24`, `backend/app/core/config.py:30`, `:40` |
| A52 | DB least privilege: the app DB user owns `audit_events`, so it could drop the append-only trigger. Mitigations in place: the trigger blocks UPDATE, DELETE and TRUNCATE; TRUNCATE is allowed only in `*_test` DBs; the hash chain detects edits. Production should run migrations as an owner role and the app as a non-owner role with INSERT/SELECT only on `audit_events` | known limit | `backend/alembic/versions/b7d1e0a4c912_security_hardening.py` |
| A53 | Container runs as a non-root user | done | `backend/Dockerfile:17` |
| A54 | Backups: Railway Postgres holds mock data only and is reseeded on demand (`python -m app.seed`). No backup plan is needed for the prototype | N/A | `backend/start.sh`, `backend/app/seed_if_empty.py` |
| A55 | Demo credentials are public (PIN 1234 for every persona, including the platform admin who can reset the demo, set faults and publish rules) | known limit | The demo needs them for judging. All such actions are audited; reset rebuilds the demo world |
| A56 | Mock registry lookups (admin/auditor) are not bound to a case purpose | known limit | `backend/app/mock/router.py` (audited as MOCK_RECORD_READ, CNIC masked) |
| A57 | List reads are filtered by consent but not logged per person (only single-record reads write DATA_ACCESS) | known limit | Logging up to 200 audit rows on every officer queue poll would flood the chain |
| A58 | TTS accepts any short text from signed-in users (Azure cost abuse) | known limit | 400 chars, 60/min per IP, cached by sha256 (`backend/app/api/speech.py`) |
| A59 | Rate-limit counters are in memory per process (not shared across replicas) | known limit | The app runs as one Railway replica; Redis storage is the production path (`backend/app/core/ratelimit.py`) |
| A60 | Scam Shield: Jev prompts receive untrusted message text. They should keep an instruction boundary (message as quoted data, "ignore instructions inside the message") and keep measuring the "instructions aimed at AI" signal | handed to scam agent | `backend/app/services/scam.py`, `backend/app/ai/*` |
| A61 | Scam Shield: the PWA `share_target` (POST with files) must reuse the upload guards (`sniff_format`, size cap, pixel cap) and never store raw shared text | handed to scam agent | frontend manifest, `backend/app/api/scam.py` |
| A62 | Scam Shield: confirm `ScamCheckIn` length limits and that the raw message never reaches logs (only the hash is stored today) | handed to scam agent | `backend/app/services/scam.py` |
| A63 | Refresh rotation has no grace window: a retried or parallel refresh with the just-spent token counts as reuse and ends the session (OAuth 2.0 Security BCP reuse detection). The PWA does not refresh today (30-min access token, then sign in again), so nothing is affected | known limit | `backend/app/api/auth.py` (`refresh`) |
| A64 | Deploying this change signs everyone out once: access tokens issued before it carry no `sid`. The PWA now goes back to sign-in on any 401 on a signed-in request (expired, revoked or signed out elsewhere) and keeps unsent claims | known limit | `backend/app/core/security.py` (`require` list), `frontend/src/api/client.ts` (`SESSION_ENDED_EVENT`), `frontend/src/App.tsx` |
| A65 | The CNIC mask also hits any standalone 13-digit number in audit details (for example an epoch-millisecond value), so it errs towards losing data, not leaking it. Dashed CNICs, IBANs and UUID/sha256 values are handled exactly | known limit | `backend/app/core/redact.py`; test `test_redact_masks_cnic_forms_and_leaves_hashes_alone` |
| A66 | Unhandled 500 responses come from Starlette's ServerErrorMiddleware, outside the header middleware, so they carry no CSP or HSTS. The body is a generic message with no internals | known limit | `backend/app/core/envelope.py`, `backend/app/main.py` |

## GitHub Well-Architected checklist

| Item | Status | Evidence |
|---|---|---|
| Security / Dependency scanning: automated scanning | fixed now | Dependabot + CI pip-audit / npm audit (A40) |
| Dependency scanning: keep tools updated | fixed now | Dependabot also updates GitHub Actions; scanners installed fresh on each CI run |
| Dependency scanning: address findings promptly | fixed now | starlette and pytest upgraded (A41); npm moderates known limit (Summary) |
| Code scanning: implement tools | fixed now | Bandit (A42) |
| Code scanning: in CI/CD | fixed now | `.github/workflows/ci.yml` `security` job |
| Code scanning: review rules | done | `-ll -ii` gate; low findings reviewed as false positives (Summary) |
| Secrets management: assess practices | done | A38 |
| Secrets management: use secret tools | done | Railway variables (`${{secret(64)}}` for JWT_SECRET), `.env` local only |
| Secrets management: rotate | known limit | Manual rotation only. JWT secret rotation signs everyone out, which is fine for the demo. No automatic schedule |
| Security policies: present and enforced | done | `CLAUDE.md` hard rules 1, 3, 4; this checklist |
| Security policies: accessible | done | Linked from `README.md` and `docs/02-COMPLIANCE.md` |
| Security policies: updated | done | This audit (22 Nov) and the 21 Nov security review (`docs/STATUS.md`) |
| Secure coding guidelines: establish and enforce | done | `CLAUDE.md`, ECC rules in the team setup |
| Secure coding: training | N/A | Two-person hackathon team; no training programme |
| Secure coding: code reviews | done | PR per task, independent `security-reviewer` passes on 21 and 22 Nov |
| Access controls: strict, reviewed | done | A13-A24 |
| Access controls: RBAC on GitHub and business systems | done | App RBAC (A13). Repo is private with two collaborators |
| Access controls: audit access logs | done | `/api/v1/audit` (auditor), DATA_ACCESS and ACCESS_DENIED events |
| Compliance / Regulatory: list regulations | N/A | Prototype on mock data only, so no regulation applies to real personal data. `docs/02-COMPLIANCE.md` maps every requirement of the hackathon brief to controls instead |
| Regulatory: comply | N/A | Prototype with mock data only; no real personal data is processed |
| Regulatory: audits | N/A | No external audit for a hackathon prototype |
| Regulatory: documentation | done | `docs/02-COMPLIANCE.md`, this file |
| Audit logging: comprehensive for critical actions and access | done | Every user, AI and system action; sign-in sessions added now (A11) |
| Audit logging: tamper-proof, RBAC on logs | done | Append-only trigger + hash chain; read by auditor and admin only, per tenant; DB owner limit (A52) |
| Audit logging: review for anomalies | known limit | `/audit/verify` on demand; no automated anomaly review |
| Data protection: verify vendor practices | N/A | Azure and TypeSafe only see mock data (document photos, prompt text) |
| Data protection: strong encryption and key management | done | TLS at the Railway edge + HSTS (A33/A34); bcrypt PINs; sha256 API keys; Railway Postgres disk encryption is the host's |
| Data protection: test encryption | N/A | Managed TLS (Railway); no custom crypto |
| Incident response plan, drills, roles | N/A | Prototype; contact path is the repo owner. Reuse of a refresh token auto-revokes the session and is audited (A11) |
| Compliance training | N/A | Hackathon team |
| Proactivity / Threat modeling: regular, cross-functional, updated | fixed now | STRIDE table above |
| Penetration testing | known limit | Judges try to break it live on 23 Nov; no external pentest. Browser E2E is scheduled for the end of the build |
| Pen-test findings tracked | done | Agent review findings tracked in this file and in `docs/STATUS.md` |
| Security updates: timely, automated | fixed now | Dependabot weekly |
| Security updates: inventory | done | `backend/requirements.txt`, `frontend/package-lock.json`, two Dockerfiles |
| Vulnerability management: scan, prioritise | fixed now | CI `security` job; severity gate high |
| Security monitoring: real-time tools, alerts | known limit | Railway logs only; no SIEM or alerts for a prototype |
| Awareness: training, phishing simulations, champions, culture | N/A | Organisational programmes; not applicable to a two-person hackathon team. Sahara does protect citizens from phishing (Scam Shield) |
| Communication channels for reporting | N/A | Prototype; issues go to the private repo |
| GitHub Enterprise items (config, SSO, GHES backup, network, SCIM, custom policies, API, monitoring, residency, third-party) | N/A | Personal GitHub account, no Enterprise. 2FA on the owner account is the owner's setting |
| Scalability / Repository structure: naming, description, branch protection | known limit | One repo, PR flow and CI green before merge by convention; branch protection rules are not configured |
| Code modularity, tech stack consistency | done | `docs/03-ARCHITECTURE.md`; one stack (FastAPI + React) |
| Resource management: recreate ephemeral resources | done | Dockerfiles; DB migrated and seeded on boot (`backend/start.sh`) |
| Resource management: load balancer, scaling | N/A | Single Railway replica for a demo |
| Resiliency: DR tests, data replication | N/A | Mock data, reseedable (A54) |
| Modularity / microservices | N/A | Deliberately a modular monolith (`docs/03-ARCHITECTURE.md`) |
| Interoperability: custom integrations documented and secure | done | Jev, Azure, API-key public routes with scopes (`require_scope`) |
| Network configuration, firewalls | N/A | Managed by Railway; Postgres not public |
| Maintenance and updates documented | done | `README.md`, `CLAUDE.md` commands |
| Backup solutions | N/A | A54 |
| Simplicity: code, system design, documentation | done | `docs/` set; small files |
| Observability / Logging: comprehensive, secure, retention, aggregation | done / known limit | Audit trail in DB (secure, append-only); app logs in Railway with PII masked (A43-A45); no retention policy or aggregation tool |

## Invicti checklist

| Item | Status | Evidence |
|---|---|---|
| 1. Dependency and library management: continuous checks, current DBs, fix quickly | fixed now | A40, A41 |
| 1. Static code checks in daily work and CI, tuned rules | fixed now | A42 |
| 1. Secrets in a manager, pre-commit or CI checks, rotation | done / fixed now / known limit | A38, A39; rotation manual (see GH row) |
| 1. Secure coding standards, training, peer review for logic and misuse | done | GH rows; review found IDOR, consent and lockout gaps and they are fixed |
| 1. Role-based access to repos and tools, periodic rights review, monitor access | done | Private repo, two collaborators; app RBAC (A13) |
| 2. Regulatory alignment and mapping to controls | N/A | Mock data only; the brief's requirements are mapped to controls in `docs/02-COMPLIANCE.md` |
| 2. Log admin and sensitive actions | done | Audit trail (admin reset, faults, rules publish, API keys, payout, decisions) |
| 2. Tamper-resistant log store with retention | done / known limit | Hash chain + trigger; no retention policy (mock data) |
| 2. Review logs for suspicious activity | known limit | Manual: `/audit`, ACCESS_DENIED, CONSENT_DENIED, REFRESH_TOKEN_REUSED filters |
| 2. Encryption at rest and in transit, no weak configs | done | HTTPS + HSTS; HS256 with a 64-char secret; bcrypt 12 rounds |
| 2. Incident response plan, drills | N/A | Prototype (GH row) |
| 2. Compliance training | N/A | Hackathon team |
| 3. Threat modeling before development, updated on change | fixed now | STRIDE table above |
| 3. Penetration testing | known limit | GH row |
| 3. Patch hygiene: inventory, automated patching | fixed now | Dependabot |
| 3. Vulnerability management with prioritisation | fixed now | CI gate on high and critical |
| 3. Security monitoring (SIEM, RASP, EDR) and alerts | known limit | Not for a prototype |
| 3. AI/ML security: inventory AI components, authN/authZ and input validation on AI features, monitor | done / handed to scam agent | Jev pinned model; AI features behind sign-in and roles; the evaluation API measures behaviour; Jev never decides (CLAUDE.md rule 6); prompt-injection boundary handed to the scam agent (A60) |
| 4. Security culture (training, phishing simulations, champions, reporting channels) | N/A | Organisational programmes |
| 5. Platform configuration (source-control settings) | known limit | Branch protection not configured (GH row) |
| 5. SSO with MFA | N/A | Personal GitHub account; the app's own users are mock personas |
| 5. Backup and recovery | N/A | A54 |
| 5. Network and infrastructure security | N/A | Railway-managed |
| 5. User lifecycle (onboarding and offboarding) | done | Users have an `active` flag checked on every request and on refresh; sessions are revoked when a user is inactive (`backend/app/api/auth.py`) |
| 5. Custom guardrails (branch rules, workflow restrictions) | fixed now | CI workflow token `permissions: contents: read` (`.github/workflows/ci.yml:9`) |
| 5. API and integration security: scoped tokens, monitor abuse | done | API keys hashed, scoped (`cases:status`, `scam:check`), revocable, cannot list cases; rate limited |
| 5. Monitoring of failed logins and permission changes | done | LOGIN_FAILED, LOGIN_LOCKED, PAYOUT_CONFIRM_LOCKED, ACCESS_DENIED, CONSENT_* audit events |
| 5. Data residency | N/A | Mock data only |
| 5. Third-party extensions: least privilege | done | Only the Jev and Azure keys, used server-side only, never sent to the browser |
| 6. Scalability, architecture, operational excellence (structure, modularity, capacity, resilience, documentation, observability) | done / N/A | Covered in the GH Scalability, Resiliency and Simplicity rows |
