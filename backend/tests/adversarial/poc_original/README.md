# Original red-team proofs of concept (21 Nov 2026)

Copied unchanged from the red-team run. They show the vulnerabilities as they
were before the security-fixes branch, so pytest does not collect them (see
`../conftest.py`). Findings: `reports/Red team findings.md` and
`reports/Security review.md` in the hackathon folder (outside this repo).

- `backend_access/`: duplicate-claim race, checkbox documents, re-decision undoing
  escalation, NULL-CNIC duplicate, closing approved cases.
- `ai_docs/`: Scam Shield steering and link tricks, forensics evasion, XFF
  rate-limit bypass, document re-upload, confirm-to-blank, blank documents.

To re-run one against old code: set `PYTHONPATH` to `backend`, set
`TEST_DATABASE_URL` to a throwaway database, and run pytest inside the folder.
