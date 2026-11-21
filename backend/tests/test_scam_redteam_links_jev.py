"""Red-team H4 (official link = exact host or real subdomain, obfuscated links found) and M5 (Jev reply validation)."""
import math

import httpx
import pytest

from app.core.config import get_settings
from app.decision.jev_client import JevClient, JevResult, JevUnavailable
from app.scam import links
from app.services import scam

FEE = "Your pension is released! Pay Rs 5000 processing fee today or it will be cancelled."


@pytest.mark.parametrize("text", ["hxxp://evil[.]com/pay", "bit.ly/3abc", "wa.me/923001234567", "evil .com/x", "evil。com/x",
                                  "t.me/pensionhelp", "evil.co/x", "evil(dot)com", "ｅｖｉｌ．ｃｏｍ"])
def test_h4_obfuscated_links_are_found(text):
    assert links.analyse_text(text)


@pytest.mark.parametrize("text", ["Open http://evil.example.com/pension.gov.example", "Open http://pension.gov.example.evil.com/login",
                                  "Open http://evil.com/?u=pension.gov.example", "Open bisp.gov.pk.evil.xyz",
                                  "Open hxxp://bisp[.]gov[.]pk[.]evil[.]xyz", "Open https://evilbisp.gov.pk.co/x"])
def test_h4_official_domain_needs_exact_host_or_real_subdomain(text):
    reports = links.analyse_text(text)
    assert reports and not any(r.official for r in reports)


@pytest.mark.parametrize("text", ["Details at https://www.bisp.gov.pk/news", "See bisp.gov.pk", "Visit pension.gov.example/status"])
def test_h4_exact_host_and_real_subdomain_are_official(text):
    reports = links.analyse_text(text)
    assert reports and all(r.official for r in reports)


@pytest.mark.parametrize("text", ["wa.me/923001234567", "t.me/pensionhelp"])
def test_h4_chat_links_are_recognised(text):
    assert "chat_link" in links.analyse_text(text)[0].findings


def test_h4_cyrillic_host_is_not_folded_into_official():
    report = links.analyse_text("Open https://bіsp.gov.pk/claim")[0]  # Cyrillic i
    assert not report.official and "non_latin" in report.findings


def test_h4_plain_sentences_are_not_links():
    assert not links.analyse_text("Thanks. Me too. See you at dinner tonight.")


@pytest.mark.parametrize("payload", [b"not json", b'{"answers": {"q": {"noul": NaN}}}', b'{"answers": {"q": {"noul": 1.5}}}',
                                     b'{"answers": {"q": {"noul": "high"}}}', b'{"answers": {"q": {"noul": true}}}',
                                     b'{"answers": []}', b'{"answers": {}}', b"[]", b'{"answers": {"q": 0.4}}'])
def test_m5_junk_answers_raise_jev_unavailable(payload):
    settings = get_settings().model_copy(update={"typesafe_api_key": "k"})
    client = JevClient(settings, transport=httpx.MockTransport(lambda r: httpx.Response(200, content=payload)))
    with pytest.raises(JevUnavailable):
        client.ask("x", {"q": {"type": "noul", "instructions": "?"}})


def test_m5_valid_answer_still_parses():
    settings = get_settings().model_copy(update={"typesafe_api_key": "k"})
    body = b'{"model": "jev-1.14.0", "answers": {"q": {"type": "noul", "noul": 0.93}}}'
    client = JevClient(settings, transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body)))
    assert client.ask("x", {"q": {"type": "noul", "instructions": "?"}}).noul("q") == 0.93


def test_m5_nan_from_jev_falls_back_and_is_never_genuine(monkeypatch):
    def ask(self, state, questions):
        return JevResult(model="m", answers={k: {"noul": math.nan} for k in questions}, latency_ms=1)
    monkeypatch.setattr("app.decision.jev_client.JevClient.ask", ask)
    result = scam.check(None, FEE, None, None, None, use_second=False)
    assert result.signals["fallback"] and all(math.isfinite(v) for v in result.signals["nouls"].values())
    assert result.verdict != "LOOKS_GENUINE"
