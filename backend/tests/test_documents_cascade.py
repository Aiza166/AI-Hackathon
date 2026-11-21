"""Document checks with the second sensor: called only when Jev is undecided or contradicts the
deterministic checks; disagreement means an officer looks (SENSORS_DISAGREE, high)."""
from PIL import Image

from app.ai.second_sensor import SensorAnswers
from app.documents import cascade_checks, indicators
from app.documents.fields import Field
from app.documents.forensics import CopyMove, ForensicReport
from app.documents.jev_checks import JevDocResult


class FakeSensor:
    def __init__(self, probabilities: dict | None, configured: bool = True):
        self.probabilities = probabilities
        self.configured = configured
        self.calls = 0

    def ask(self, questions, untrusted_text=None, image_jpeg=None):
        self.calls += 1
        assert image_jpeg and image_jpeg.startswith(b"\xff\xd8")
        return SensorAnswers(status="ok", model="gpt-4o-mini", probabilities={q: self.probabilities.get(q, 0.05) for q in questions},
                             note="AI-written, advisory: The seal looks sharp.", latency_ms=900, cost_usd=0.0004)


def report(copy_move: bool = False, stamps: int = 0) -> ForensicReport:
    return ForensicReport(CopyMove(found=copy_move, score=0.8 if copy_move else 0.0, stamp_candidates=stamps), 1.0, 2.0, {}, False)


def jev(answers: dict) -> JevDocResult:
    return JevDocResult(status="ok", model="jev-1.14.0", latency_ms=800,
                        answers={k: {"p": p, "band": "yes" if p > 0.7 else "no" if p < 0.3 else "undecided"} for k, p in answers.items()})


IMG = Image.new("RGB", (600, 400), "white")
CNIC = {"cnic": Field(value="9000000000022", confidence=0.95, method="label")}


def test_clear_jev_that_agrees_with_rules_skips_the_second_sensor():
    sensor = FakeSensor({})
    out = cascade_checks.run("claimant_cnic", IMG, CNIC, report(), jev({"right_type": 0.95, "text_altered": 0.1}), sensor)
    assert sensor.calls == 0 and out.second is None
    assert [s["status"] for s in out.sensors] == ["ok", "ok", "not_needed"]


def test_undecided_text_altered_is_resolved_by_second_sensor():
    sensor = FakeSensor({"right_type": 0.95, "text_altered": 0.05})
    out = cascade_checks.run("claimant_cnic", IMG, CNIC, report(), jev({"right_type": 0.95, "text_altered": 0.45}), sensor)
    assert sensor.calls == 1 and out.fused.resolved == ["text_altered"]
    codes = [i.code for i in indicators.from_jev(out.jev)]
    assert "JEV_UNDECIDED" not in codes and "TEXT_LOOKS_ALTERED" not in codes


def test_jev_missing_a_pasted_stamp_against_second_sensor_agreeing_with_copy_move_is_a_disagreement():
    sensor = FakeSensor({"right_type": 0.9, "text_altered": 0.9, "stamp_present": 0.9})
    out = cascade_checks.run("death_certificate", IMG, {}, report(copy_move=True, stamps=2),
                             jev({"right_type": 0.9, "text_altered": 0.1, "stamp_present": 0.9}), sensor)
    assert out.fused.disagreements == ["text_altered"]
    assert out.summary()["second_sensor"]["note"].startswith("AI-written, advisory")


def test_jev_down_second_sensor_stands_in():
    sensor = FakeSensor({"right_type": 0.05, "text_altered": 0.05})
    skipped = JevDocResult(status="skipped", note="Jev not configured")
    out = cascade_checks.run("claimant_cnic", IMG, {}, report(), skipped, sensor)
    assert out.jev.status == "ok" and out.jev.model == "gpt-4o-mini"
    # One AI sensor alone may not raise a flag: it becomes officer info instead.
    assert "WRONG_DOCUMENT" not in [i.code for i in indicators.from_jev(out.jev)]
    assert out.second_only_flags == ["right_type"]


def test_not_configured_changes_nothing():
    original = jev({"right_type": 0.5, "text_altered": 0.45})
    out = cascade_checks.run("claimant_cnic", IMG, CNIC, report(), original, FakeSensor({}, configured=False))
    assert out.jev == original and out.second is None and [s["name"] for s in out.sensors] == ["deterministic", "jev"]


def test_sensors_disagree_indicator_is_high_and_officer_only():
    ind = indicators.make("SENSORS_DISAGREE", questions=["text_altered"])
    assert ind.severity == "high" and ind.citizen_visible is False
    assert "fake" not in ind.text_en.lower() and "forged" not in ind.text_en.lower()


class DownSensor(FakeSensor):
    def ask(self, questions, untrusted_text=None, image_jpeg=None):
        self.calls += 1
        return SensorAnswers(status="unavailable", error="ConnectTimeout", latency_ms=8000)


def test_second_sensor_down_keeps_jevs_answers_unchanged():
    original = jev({"right_type": 0.95, "text_altered": 0.45})
    out = cascade_checks.run("death_certificate", IMG, {}, report(), original, DownSensor({}))
    assert out.jev == original and out.second.status == "unavailable"
    assert out.sensors[-1]["status"] == "unavailable"


def test_second_sensor_alone_cannot_raise_a_document_flag():
    sensor = FakeSensor({"right_type": 0.05, "text_altered": 0.95})
    out = cascade_checks.run("claimant_cnic", IMG, {}, report(), jev({"right_type": 0.5, "text_altered": 0.5}), sensor)
    codes = [i.code for i in indicators.from_jev(out.jev)]
    assert "WRONG_DOCUMENT" not in codes and "TEXT_LOOKS_ALTERED" not in codes
    assert sorted(out.second_only_flags) == ["right_type", "text_altered"]
    flag = indicators.make("SECOND_SENSOR_FLAG", questions=out.second_only_flags)
    assert flag.severity == "info" and flag.citizen_visible is False
