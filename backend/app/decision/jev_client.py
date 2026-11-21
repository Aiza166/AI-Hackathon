"""Thin client for Jev (TypeSafe System One API).

Wire format follows the official OpenAPI spec (docs.typesafe.ai/api/system-one.md):
POST {base}/v1/systemone, Bearer auth, body {model, state, questions}.
Jev is used as a sensor only: callers turn probabilities into decisions in code.
"""
import math
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx

from app.core.config import Settings, get_settings

# TypeSafe guidance: above 0.7 is yes, below 0.3 is no, between is undecided.
NOUL_YES = 0.7
NOUL_NO = 0.3
IMAGES_HEADER = "TypeSafe-Danger-Zone-Images"  # required for any request with images or Box questions


class Band(StrEnum):
    YES = "yes"
    NO = "no"
    UNDECIDED = "undecided"


def noul_band(probability: float) -> Band:
    if probability > NOUL_YES:
        return Band.YES
    if probability < NOUL_NO:
        return Band.NO
    return Band.UNDECIDED


class JevUnavailable(Exception):
    """Jev did not answer in time or returned an error. Callers must route to UNSURE."""


@dataclass(frozen=True)
class JevResult:
    model: str  # the versioned model that actually answered: always log this
    answers: dict[str, Any]
    latency_ms: int
    usage: dict[str, int] = field(default_factory=dict)

    def noul(self, name: str) -> float:
        return valid_probability(self.answers[name]["noul"])


def noul(instructions: str) -> dict:
    return {"type": "noul", "instructions": instructions}


def box(instructions: str) -> dict:
    """Always returns a box, even if the target is absent: pair it with a presence Noul."""
    return {"type": "box", "instructions": instructions}


def choice(instructions: str, criteria: dict[str, str]) -> dict:
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def valid_probability(value: Any) -> float:
    """A Noul must be a finite number in [0, 1]; anything else (NaN, inf, text, bool) is rejected."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("noul is not a number")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError("noul is outside 0..1")
    return number


def _model_of(data: Any) -> str:
    if not isinstance(data, dict):
        raise TypeError("Jev answer is not an object")
    model = data.get("model", "unknown")
    return model if isinstance(model, str) and model else "unknown"


def _validated_answers(data: dict, questions: dict[str, dict]) -> dict[str, Any]:
    answers = data.get("answers")
    if not isinstance(answers, dict):
        raise TypeError("answers is not an object")
    checked: dict[str, Any] = {}
    for name, question in questions.items():
        answer = answers[name]  # a missing answer is a KeyError, so the whole call is unusable
        if not isinstance(answer, dict):
            raise TypeError("answer is not an object")
        if question.get("type") == "noul":
            answer = {**answer, "noul": valid_probability(answer.get("noul"))}
        checked[name] = answer
    return checked


class JevClient:
    def __init__(self, settings: Settings | None = None, transport: httpx.BaseTransport | None = None):
        self._settings = settings or get_settings()
        self._client = httpx.Client(
            base_url=self._settings.typesafe_base_url,
            timeout=self._settings.jev_timeout_seconds,
            transport=transport,
        )

    def ask(self, state: Any, questions: dict[str, dict], assets: dict[str, dict] | None = None, timeout: float | None = None) -> JevResult:
        """assets: images referenced by key from state/instructions (needs the Danger-Zone header)."""
        if not self._settings.typesafe_api_key:
            raise JevUnavailable("TYPESAFE_API_KEY is not set")
        body = {"model": self._settings.jev_model, "state": state, "questions": questions}
        headers = {"Authorization": f"Bearer {self._settings.typesafe_api_key}"}
        if assets:
            body["assets"] = assets
            headers[IMAGES_HEADER] = "true"
        started = time.perf_counter()
        try:
            response = self._client.post("/v1/systemone", json=body, headers=headers, timeout=timeout or self._settings.jev_timeout_seconds)
            response.raise_for_status()
            data = response.json()
            result = JevResult(
                model=_model_of(data),
                answers=_validated_answers(data, questions),
                latency_ms=int((time.perf_counter() - started) * 1000),
                usage=data.get("usage") if isinstance(data.get("usage"), dict) else {},
            )
        except httpx.HTTPError as exc:
            # Never include the response body or key in the message.
            raise JevUnavailable(f"Jev call failed: {type(exc).__name__}") from exc
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            # Junk, truncated or wrongly shaped answers: callers fall back exactly as for an outage.
            raise JevUnavailable(f"Jev answer was not usable: {type(exc).__name__}") from exc
        return result

    def reachable(self) -> bool:
        """Cheap health check (lists models, no tokens used). Never raises."""
        if not self._settings.typesafe_api_key:
            return False
        try:
            headers = {"Authorization": f"Bearer {self._settings.typesafe_api_key}"}
            return self._client.get("/v1/models", headers=headers).status_code == 200
        except httpx.HTTPError:
            return False

    def close(self) -> None:
        self._client.close()
