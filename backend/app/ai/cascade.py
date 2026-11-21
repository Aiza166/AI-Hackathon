"""Sensor cascade: Jev + deterministic checks first, the second sensor only when needed.

Used by Scam Shield and by the document Jev checks. Code decides; the sensors answer
small factual yes/no questions.

When is the second sensor called (triggers)? For a decisive question, when
  - Jev is undecided (0.3-0.7), or
  - Jev's clear answer contradicts a deterministic hint (e.g. Jev says "no link" but the
    URL parser found one), or
  - Jev is unavailable (the second sensor then stands in, under the same rules).

How are answers fused (per decisive question)?
  - Jev clear, no conflict          -> Jev's value, second sensor not consulted.
  - Jev undecided/missing           -> the second sensor's clear answer is used if no
                                       deterministic hint contradicts it; a contradiction
                                       is a disagreement; an undecided answer stays undecided.
  - Jev clear but contradicts rules -> second sensor agrees with Jev: proceed with Jev;
                                       it sides with the rules or is undecided: disagreement.
  - second sensor not available     -> Jev's value; a conflict stays "unresolved" (the
                                       behaviour without a second sensor).
A disagreement always means "not sure": the caller routes to UNSURE / NOT_SURE (a person).
"""
from dataclasses import dataclass, field

from app.ai.second_sensor import SensorAnswers
from app.decision.jev_client import Band, noul_band

UNKNOWN = 0.5  # a missing answer is exactly "undecided"


@dataclass(frozen=True)
class Fused:
    probabilities: dict[str, float]
    triggers: list[str] = field(default_factory=list)
    resolved: list[str] = field(default_factory=list)  # Jev undecided/missing, second sensor answered clearly
    disagreements: list[str] = field(default_factory=list)  # sensors or sensor-vs-rules disagree -> not sure
    unresolved: list[str] = field(default_factory=list)  # conflict seen but no second sensor to break it

    def to_dict(self) -> dict:
        return {"triggers": self.triggers, "resolved": self.resolved, "disagreements": self.disagreements,
                "unresolved": self.unresolved}


def _conflict(band: Band, hint: bool | None) -> bool:
    return hint is not None and band != Band.UNDECIDED and (band == Band.YES) != hint


def triggers(jev: dict[str, float] | None, hints: dict[str, bool | None], decisive: list[str]) -> list[str]:
    if jev is None:
        return ["jev_unavailable"]
    out = []
    for q in decisive:
        band = noul_band(jev.get(q, UNKNOWN))
        if band == Band.UNDECIDED:
            out.append(f"jev_undecided:{q}")
        elif _conflict(band, hints.get(q)):
            out.append(f"jev_vs_rules:{q}")
    return out


def fuse(jev: dict[str, float] | None, hints: dict[str, bool | None], second: SensorAnswers | None,
         decisive: list[str]) -> Fused:
    fired = triggers(jev, hints, decisive)
    base = dict(jev) if jev is not None else {}
    probabilities = {**base}
    resolved, disagreements, unresolved = [], [], []
    second_ok = second is not None and second.status == "ok"
    for q in decisive:
        jev_p = base.get(q, UNKNOWN)
        jev_band = noul_band(jev_p)
        hint = hints.get(q)
        conflict = _conflict(jev_band, hint)
        probabilities[q] = jev_p
        if jev_band != Band.UNDECIDED and not conflict:
            continue
        if not second_ok or q not in second.probabilities:
            if conflict:
                unresolved.append(q)
            continue
        sp = second.probabilities[q]
        s_band = noul_band(sp)
        if jev_band == Band.UNDECIDED:
            if s_band == Band.UNDECIDED:
                continue
            if _conflict(s_band, hint):
                disagreements.append(q)
            else:
                probabilities[q] = sp
                resolved.append(q)
        elif s_band != jev_band:  # Jev clear and conflicting with rules: second sensor did not back Jev
            disagreements.append(q)
    if second_ok:  # non-decisive questions Jev could not answer: take the second sensor's value
        for q, sp in second.probabilities.items():
            probabilities.setdefault(q, sp)
    return Fused(probabilities, fired, resolved, disagreements, unresolved)
