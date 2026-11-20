import json

import httpx
import pytest

from app.core.config import Settings
from app.decision.jev_client import Band, JevClient, JevUnavailable, noul, noul_band


def _settings(**overrides) -> Settings:
    base = {"typesafe_api_key": "test-key", "jev_model": "jev-1.14.0"}
    return Settings(**{**base, **overrides})


@pytest.mark.parametrize(
    ("probability", "expected"),
    [(0.95, Band.YES), (0.71, Band.YES), (0.7, Band.UNDECIDED), (0.5, Band.UNDECIDED), (0.3, Band.UNDECIDED), (0.29, Band.NO), (0.0, Band.NO)],
)
def test_noul_band_follows_typesafe_guidance(probability, expected):
    assert noul_band(probability) is expected


def test_ask_sends_pinned_model_and_returns_answering_model():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers["Authorization"]
        return httpx.Response(200, json={"model": "jev-1.14.0", "answers": {"fee": {"type": "noul", "noul": 0.93}}, "usage": {"input_tokens": 50, "output_tokens": 3}})

    client = JevClient(_settings(), transport=httpx.MockTransport(handler))

    result = client.ask("Pay Rs 5000 fee to release your pension", {"fee": noul("Does it ask for a fee?")})

    assert seen["body"]["model"] == "jev-1.14.0"
    assert seen["body"]["questions"]["fee"] == {"type": "noul", "instructions": "Does it ask for a fee?"}
    assert seen["auth"] == "Bearer test-key"
    assert result.model == "jev-1.14.0"
    assert result.noul("fee") == pytest.approx(0.93)


def test_ask_without_key_is_unavailable_not_a_guess():
    client = JevClient(_settings(typesafe_api_key=None))

    with pytest.raises(JevUnavailable):
        client.ask("text", {"q": noul("?")})


def test_server_error_becomes_unavailable():
    client = JevClient(_settings(), transport=httpx.MockTransport(lambda r: httpx.Response(503)))

    with pytest.raises(JevUnavailable):
        client.ask("text", {"q": noul("?")})
