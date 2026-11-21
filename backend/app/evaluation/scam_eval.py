"""Scam Shield evaluation (Challenge 8) on a labelled, invented message set, per sensor tier.

Tiers (the same `services.scam.check`, with sensors switched on or off):
  deterministic  keyword fallback + link checks + caller checks; no AI (fast, offline)
  jev_only       Jev answers only; no link/caller rules, no second sensor
  cascade        Jev + deterministic checks + the second sensor when the cascade triggers
Offline (default) only the deterministic tier runs; live=True also runs the Jev tiers
(needs TYPESAFE_API_KEY; the second sensor joins only if SECOND_SENSOR_* is set).
Tests run every tier with the sensors mocked.

Positive class = scam. FPR = genuine messages called LIKELY_SCAM. FNR = scam messages
called LOOKS_GENUINE (the dangerous miss). NOT_SURE is neither: it is the undecided rate
(the citizen is told to ask a helper or officer). accuracy = correct verdicts / all
(scam -> LIKELY_SCAM, genuine -> LOOKS_GENUINE), so every NOT_SURE counts as not correct.
"""
import json
import statistics
import time
from pathlib import Path

from app.core.config import get_settings
from app.services import scam as scam_service

DATA_FILE = Path(__file__).resolve().parent.parent / "eval_data" / "scam_messages.json"
TIERS = {
    "deterministic": {"use_jev": False, "use_rules": True, "use_second": False},
    "jev_only": {"use_jev": True, "use_rules": False, "use_second": False},
    "cascade": {"use_jev": True, "use_rules": True, "use_second": True},
}
OFFLINE_TIERS = ("deterministic",)


def load_messages() -> list[dict]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))["messages"]


def _share(items: list[dict], verdict: str) -> float:
    return round(sum(r["verdict"] == verdict for r in items) / len(items), 4) if items else 0.0


def _rates(rows: list[dict]) -> dict:
    scams = [r for r in rows if r["label"] == "scam"]
    genuine = [r for r in rows if r["label"] == "genuine"]
    correct = sum((r["label"] == "scam" and r["verdict"] == "LIKELY_SCAM") or (r["label"] == "genuine" and r["verdict"] == "LOOKS_GENUINE")
                  for r in rows)
    return {
        "n": len(rows), "n_scam": len(scams), "n_genuine": len(genuine),
        "accuracy": round(correct / len(rows), 4) if rows else 0.0,
        "fpr": _share(genuine, "LIKELY_SCAM"), "fnr": _share(scams, "LOOKS_GENUINE"),
        "scam_caught_rate": _share(scams, "LIKELY_SCAM"), "genuine_passed_rate": _share(genuine, "LOOKS_GENUINE"),
        "not_sure_rate": _share(rows, "NOT_SURE"),
        "not_sure_rate_scam": _share(scams, "NOT_SURE"), "not_sure_rate_genuine": _share(genuine, "NOT_SURE"),
    }


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))] if ordered else 0.0


def _run_tier(name: str, messages: list[dict]) -> tuple[dict, list[dict]]:
    rows = []
    for msg in messages:
        started = time.perf_counter()
        result = scam_service.check(None, msg["text"], msg["sender"], None, None, channel=msg.get("channel", "sms"), **TIERS[name])
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        ran = {s["name"]: s.get("status") for s in result.signals["sensors"]}
        rows.append({"id": msg["id"], "lang": msg["lang"], "channel": msg.get("channel", "sms"), "label": msg["label"],
                     "verdict": result.verdict, "score": result.score, "fallback": result.signals["fallback"],
                     "model_id": result.model_id, "latency_ms": latency_ms, "cost_usd": result.cost_usd,
                     "second_sensor_ran": ran.get("second_sensor") == "ok",
                     "disagreement": bool(result.signals["cascade"] and result.signals["cascade"]["disagreements"])})
    latencies = [r["latency_ms"] for r in rows]
    cost = round(sum(r["cost_usd"] for r in rows), 6)
    models = sorted({r["model_id"] for r in rows if r["model_id"]})
    metrics = {
        "tier": name, "status": "ran", **_rates(rows),
        "median_latency_ms": statistics.median(latencies), "p95_latency_ms": _p95(latencies),
        "total_cost_usd": cost, "cost_per_check_usd": round(cost / len(rows), 8) if rows else 0.0,
        "second_sensor_calls": sum(r["second_sensor_ran"] for r in rows),
        "disagreements": sum(r["disagreement"] for r in rows),
        "fallback_count": sum(r["fallback"] for r in rows),
        "model_id": models[0] if len(models) == 1 else (models or None),
        "by_language": {lang: _rates([r for r in rows if r["lang"] == lang]) for lang in sorted({r["lang"] for r in rows})},
        "by_channel": {ch: _rates([r for r in rows if r["channel"] == ch]) for ch in sorted({r["channel"] for r in rows})},
    }
    return metrics, rows


def evaluate_scam(live: bool = False, tiers: tuple[str, ...] | None = None) -> dict:
    """live=True runs the Jev tiers against the real API. `tiers` forces a set (tests, with mocks)."""
    selected = tiers or (tuple(TIERS) if live else OFFLINE_TIERS)
    messages = load_messages()
    results: dict[str, dict] = {}
    tier_rows: dict[str, list[dict]] = {}
    items: dict[str, dict] = {m["id"]: {"id": m["id"], "lang": m["lang"], "channel": m.get("channel", "sms"),
                                        "label": m["label"], "tier_verdicts": {}} for m in messages}
    for name in TIERS:
        if name not in selected:
            results[name] = {"tier": name, "status": "not_run", "reason": "needs the Jev API key (live run)"}
            continue
        metrics, rows = _run_tier(name, messages)
        if name == "cascade" and not get_settings().second_sensor_configured:
            metrics["note"] = "second sensor not configured: cascade = Jev + deterministic checks"
        results[name] = metrics
        tier_rows[name] = rows
        for row in rows:
            items[row["id"]]["tier_verdicts"][name] = row["verdict"]
    primary_name = "cascade" if "cascade" in selected else selected[0]
    primary = results[primary_name]
    primary_rows = [{**row, "tier_verdicts": items[row["id"]]["tier_verdicts"]} for row in tier_rows[primary_name]]
    return {
        "mode": "live" if live else ("keyword_fallback" if primary_name == "deterministic" else "mocked"),
        "primary_tier": primary_name,
        **{k: primary[k] for k in ("n", "n_scam", "n_genuine", "accuracy", "fpr", "fnr", "scam_caught_rate", "genuine_passed_rate",
                                   "not_sure_rate", "not_sure_rate_scam", "not_sure_rate_genuine", "median_latency_ms",
                                   "fallback_count", "model_id", "by_language")},
        "tiers": results,
        "items": primary_rows,
    }
