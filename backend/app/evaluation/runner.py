"""Run all three evaluations and keep the last result.

The last result is held in memory. If nothing has run in this process yet,
`latest()` serves the committed sample in backend/results/eval_latest.json.
Regenerate that file with:  python -m app.evaluation.runner
"""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.evaluation.claims import evaluate_claims
from app.evaluation.names import evaluate_names
from app.evaluation.scam_eval import evaluate_scam

BACKEND_DIR = Path(__file__).resolve().parents[2]
RULESET_FILE = BACKEND_DIR / "app" / "decision" / "rulesets" / "survivor_pension_v1.json"
RESULTS_FILE = BACKEND_DIR / "results" / "eval_latest.json"

_lock = threading.Lock()
_latest: dict | None = None


def default_ruleset() -> dict:
    return json.loads(RULESET_FILE.read_text(encoding="utf-8"))


def summary(result: dict) -> dict:
    """The headline numbers (also stored in the audit event)."""
    claims, names, scam = result["claims"], result["names"], result["scam"]
    return {
        "ruleset_version": result["ruleset_version"],
        "min_cost_threshold": claims["min_cost"]["threshold"],
        "min_cost": claims["min_cost"]["total_cost"],
        "cost_at_configured": claims["at_configured"]["total_cost"],
        "wrong_approvals_at_configured": claims["at_configured"]["wrong_approvals"],
        "wrong_approvals_by_kind": claims["wrong_approvals_by_kind_at_configured"],
        "human_review_rate_at_configured": claims["at_configured"]["needs_person_rate"],
        "name_false_match_rate": names["false_match_rate"],
        "name_false_non_match_rate": names["false_non_match_rate"],
        "scam_mode": scam["mode"], "scam_fpr": scam["fpr"], "scam_fnr": scam["fnr"],
        "scam_not_sure_rate": scam["not_sure_rate"],
    }


def run_all(ruleset: dict | None = None, *, live_scam: bool = False) -> dict:
    global _latest
    ruleset = ruleset or default_ruleset()
    result = {
        "prototype": True,
        "note": "Synthetic mock data only. Numbers describe this prototype on invented cases, not real-world accuracy.",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ruleset_version": ruleset.get("version"),
        "claims": evaluate_claims(ruleset),
        "names": evaluate_names(),
        "scam": evaluate_scam(live=live_scam),
    }
    result["summary"] = summary(result)
    with _lock:
        _latest = result
    return result


def latest() -> dict | None:
    with _lock:
        if _latest is not None:
            return _latest
    if RESULTS_FILE.exists():
        return {**json.loads(RESULTS_FILE.read_text(encoding="utf-8")), "source": "committed_sample"}
    return None


def write_results(result: dict, path: Path = RESULTS_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=1, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_results(run_all())
    print(json.dumps(latest()["summary"], indent=1))  # noqa: T201 - CLI output
