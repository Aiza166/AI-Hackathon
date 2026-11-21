"""Document checks evaluation per sensor tier on backend/sample_docs (20 mock images).

Label: positive = the edited death certificate (original + WhatsApp copy, per manifest.json);
every other image is a clean original, WhatsApp copy or screenshot. Each image is checked
as its correct document kind. A tier "flags" an image when it would send it for a second
look (severity high or mismatch); "undecided" when it is left with an undecided decisive
answer and nothing flagged.

Tiers:
  deterministic  stamp copy-move forensics (no OCR/registry here: those need the database)
  jev_only       Jev's question set B on the image
  cascade        forensics + Jev + the second sensor when the cascade triggers
Offline only the deterministic tier runs; live=True adds the Jev tiers (needs keys).
"""
import json
import statistics
import time
from pathlib import Path

from app.core.config import get_settings
from app.documents import cascade_checks, forensics, indicators, jev_checks
from app.documents.imaging import load

SAMPLE_DIR = Path(__file__).resolve().parents[2] / "sample_docs"
TIERS = ("deterministic", "jev_only", "cascade")
FLAG_SEVERITIES = ("high", "mismatch")


def kind_for(doc: str) -> str:
    if doc.startswith("cnic_front_aslam"):
        return "deceased_cnic"
    if doc.startswith("cnic"):
        return "claimant_cnic"
    if doc.startswith("death_certificate"):
        return "death_certificate"
    if doc.startswith("frc"):
        return "frc"
    return "nikah_nama"


def _outcome(found: list, undecided: bool) -> str:
    if any(i.severity in FLAG_SEVERITIES for i in found):
        return "flag"
    return "undecided" if undecided else "pass"


def _check(tier: str, kind: str, image, report: forensics.ForensicReport) -> tuple[str, int, float]:
    if tier == "deterministic":
        return _outcome(indicators.from_forensics(report), False), 0, 0.0
    jev = jev_checks.ask_document_questions(kind, image)
    if tier == "jev_only":
        found = indicators.from_jev(jev)
        undecided = jev.status != "ok" or any(i.code == "JEV_UNDECIDED" for i in found)
        return _outcome(found, undecided), jev.latency_ms or 0, 0.0
    sensed = cascade_checks.run(kind, image, {}, report, jev)
    found = [*indicators.from_forensics(report), *indicators.from_jev(sensed.jev)]
    if sensed.fused and sensed.fused.disagreements:
        found.append(indicators.make("SENSORS_DISAGREE"))
    undecided = any(i.code == "JEV_UNDECIDED" for i in found) or sensed.jev.status != "ok"
    latency = sum(s.get("latency_ms") or 0 for s in sensed.sensors)
    cost = sum(s.get("cost_usd") or 0.0 for s in sensed.sensors)
    return _outcome(found, undecided), latency, cost


def _metrics(rows: list[dict]) -> dict:
    pos = [r for r in rows if r["edited"]]
    neg = [r for r in rows if not r["edited"]]
    correct = sum((r["edited"] and r["outcome"] == "flag") or (not r["edited"] and r["outcome"] == "pass") for r in rows)
    share = lambda items, outcome: round(sum(r["outcome"] == outcome for r in items) / len(items), 4) if items else 0.0  # noqa: E731
    latencies = [r["latency_ms"] for r in rows]
    cost = round(sum(r["cost_usd"] for r in rows), 6)
    return {"n": len(rows), "n_edited": len(pos), "accuracy": round(correct / len(rows), 4) if rows else 0.0,
            "fpr": share(neg, "flag"), "fnr": share(pos, "pass"), "undecided_rate": share(rows, "undecided"),
            "median_latency_ms": statistics.median(latencies) if latencies else 0, "total_cost_usd": cost}


def evaluate_documents(live: bool = False, tiers: tuple[str, ...] | None = None) -> dict:
    selected = tiers or (TIERS if live else ("deterministic",))
    manifest = json.loads((SAMPLE_DIR / "manifest.json").read_text(encoding="utf-8"))["files"]
    loaded = []
    for entry in manifest:
        img = load((SAMPLE_DIR / entry["file"]).read_bytes()).image
        started = time.perf_counter()
        report, _ = forensics.analyse(img, {})
        loaded.append((entry, img, report, round((time.perf_counter() - started) * 1000, 1)))
    out: dict[str, dict] = {}
    for tier in TIERS:
        if tier not in selected:
            out[tier] = {"tier": tier, "status": "not_run", "reason": "needs the Jev API key (live run)"}
            continue
        rows = []
        for entry, img, report, forensic_ms in loaded:
            outcome, latency, cost = _check(tier, kind_for(entry["doc"]), img, report)
            rows.append({"file": entry["file"], "variant": entry["variant"], "edited": entry["edited"], "outcome": outcome,
                         "latency_ms": latency + forensic_ms * (tier != "jev_only"), "cost_usd": cost})
        out[tier] = {"tier": tier, "status": "ran", **_metrics(rows), "items": rows}
        if tier == "cascade" and not get_settings().second_sensor_configured:
            out[tier]["note"] = "second sensor not configured: cascade = forensics + Jev"
    return {"set": "backend/sample_docs", "positive": "edited document", "tiers": out}
