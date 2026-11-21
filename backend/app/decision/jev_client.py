"""Thin client for Jev (TypeSafe System One API).

Wire format follows the official OpenAPI spec (docs.typesafe.ai/api/system-one.md):
POST {base}/v1/systemone, Bearer auth, body {model, state, questions}.
Jev is used as a sensor only: callers turn probabilities into decisions in code.
"""
import ssl
import time
from dataclasses import dataclass, field
from functools import lru_cache
from enum import StrEnum
from typing import Any

import httpx

from app.core import outages
from app.core.config import Settings, get_settings

# TypeSafe guidance: above 0.7 is yes, below 0.3 is no, between is undecided.
NOUL_YES = 0.7
NOUL_NO = 0.3
IMAGES_HEADER = "TypeSafe-Danger-Zone-Images"  # required for any request with images or Box questions


@lru_cache(maxsize=1)
def shared_ssl_context() -> ssl.SSLContext:
    """Building a verified TLS context loads the CA bundle (~0.5 s on Windows); do it once per process."""
    return httpx.create_ssl_context()


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
        return float(self.answers[name]["noul"])


def noul(instructions: str) -> dict:
    return {"type": "noul", "instructions": instructions}


def box(instructions: str) -> dict:
    """Always returns a box, even if the target is absent: pair it with a presence Noul."""
    return {"type": "box", "instructions": instructions}


def choice(instructions: str, criteria: dict[str, str]) -> dict:
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


class JevClient:
    def __init__(self, settings: Settings | None = None, transport: httpx.BaseTransport | None = None):
        self._settings = settings or get_settings()
        self._client = httpx.Client(
            base_url=self._settings.typesafe_base_url,
            timeout=self._settings.jev_timeout_seconds,
            transport=transport,
            verify=shared_ssl_context(),
        )

    def ask(self, state: Any, questions: dict[str, dict], assets: dict[str, dict] | None = None, timeout: float | None = None) -> JevResult:
        """assets: images referenced by key from state/instructions (needs the Danger-Zone header)."""
        if not self._settings.typesafe_api_key:
            raise JevUnavailable("TYPESAFE_API_KEY is not set")
        if outages.is_down("jev"):
            raise JevUnavailable("simulated outage (judge console)")
        body = {"model": self._settings.jev_model, "state": state, "questions": questions}
        headers = {"Authorization": f"Bearer {self._settings.typesafe_api_key}"}
        if assets:
            body["assets"] = assets
            headers[IMAGES_HEADER] = "true"
        started = time.perf_counter()
        try:
            response = self._client.post("/v1/systemone", json=body, headers=headers, timeout=timeout or self._settings.jev_timeout_seconds)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            # Never include the response body or key in the message.
            raise JevUnavailable(f"Jev call failed: {type(exc).__name__}") from exc
        latency_ms = int((time.perf_counter() - started) * 1000)
        data = response.json()
        return JevResult(
            model=data.get("model", "unknown"),
            answers=data.get("answers", {}),
            latency_ms=latency_ms,
            usage=data.get("usage", {}),
        )

    def reachable(self) -> bool:
        """Cheap health check (lists models, no tokens used). Never raises."""
        if not self._settings.typesafe_api_key or outages.is_down("jev"):
            return False
        try:
            headers = {"Authorization": f"Bearer {self._settings.typesafe_api_key}"}
            return self._client.get("/v1/models", headers=headers).status_code == 200
        except httpx.HTTPError:
            return False

    def close(self) -> None:
        self._client.close()
