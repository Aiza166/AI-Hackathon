"""Scam Shield evaluation (Challenge 8) on a small labelled, invented message set.

Default: Jev is switched off, so every message goes through the keyword
fallback (fast, offline, deterministic). live=True asks the real Jev
(needs TYPESAFE_API_KEY); if Jev fails on a message, that message falls back
and is counted in `fallback_count`.

Positive class = scam. FPR = genuine messages called LIKELY_SCAM.
FNR = scam messages called LOOKS_GENUINE (the dangerous miss).
NOT_SURE is neither: the citizen is told to ask a helper or officer.
"""
import json
import statistics
import time
from pathlib import Path

from app.services import scam as scam_service

DATA_FILE = Path(__file__).resolve().parent.parent / "eval_data" / "scam_messages.json"


def load_messages() -> list[dict]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))["messages"]


def _rates(rows: list[dict]) -> dict:
    scams = [r for r in rows if r["label"] == "scam"]
    genuine = [r for r in rows if r["label"] == "genuine"]

    def share(items: list[dict], verdict: str) -> float:
        return round(sum(r["verdict"] == verdict for r in items) / len(items), 4) if items else 0.0

    return {
        "n": len(rows), "n_scam": len(scams), "n_genuine": len(genuine),
        "fpr": share(genuine, "LIKELY_SCAM"), "fnr": share(scams, "LOOKS_GENUINE"),
        "scam_caught_rate": share(scams, "LIKELY_SCAM"), "genuine_passed_rate": share(genuine, "LOOKS_GENUINE"),
        "not_sure_rate": share(rows, "NOT_SURE"),
        "not_sure_rate_scam": share(scams, "NOT_SURE"), "not_sure_rate_genuine": share(genuine, "NOT_SURE"),
    }


def evaluate_scam(live: bool = False) -> dict:
    rows = []
    for msg in load_messages():
        started = time.perf_counter()
        result = scam_service.check(None, msg["text"], msg["sender"], None, None, use_jev=live)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        rows.append({"id": msg["id"], "lang": msg["lang"], "label": msg["label"], "verdict": result.verdict,
                     "score": result.score, "fallback": result.signals["fallback"], "model_id": result.model_id,
                     "latency_ms": latency_ms})
    langs = sorted({r["lang"] for r in rows})
    models = sorted({r["model_id"] for r in rows if r["model_id"]})
    return {
        "mode": "live_jev" if live else "keyword_fallback",
        **_rates(rows),
        "median_latency_ms": statistics.median(r["latency_ms"] for r in rows),
        "model_id": models[0] if len(models) == 1 else (models or None),
        "fallback_count": sum(r["fallback"] for r in rows),
        "by_language": {lang: _rates([r for r in rows if r["lang"] == lang]) for lang in langs},
        "items": rows,
    }
