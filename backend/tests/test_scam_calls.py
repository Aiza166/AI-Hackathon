"""Caller / sender checks: official short codes are evidence, never proof."""
from app.scam import calls


def test_mock_official_sender_is_recognised():
    report = calls.analyse_caller("pension-gov", channel="sms")
    assert report.official_label == "mock"
    assert report.findings == ()


def test_real_short_code_sms_is_official_reference():
    report = calls.analyse_caller("8171", channel="sms")
    assert report.official_label == "real-world reference"
    assert "spoofable" in report.notes


def test_official_sms_code_placing_a_call_is_a_red_flag():
    report = calls.analyse_caller("8171", channel="call")
    assert "official_code_calling" in report.findings


def test_personal_mobile_numbers_are_normalised_and_flagged():
    assert calls.analyse_caller("+92 300 0000000", channel="call").normalised == "03000000000"
    assert "personal_mobile" in calls.analyse_caller("0300-0000000", channel="whatsapp").findings


def test_international_and_hidden_numbers():
    assert "international" in calls.analyse_caller("+44 7000 000000", channel="call").findings
    assert "hidden_number" in calls.analyse_caller("Private number", channel="call").findings
    assert calls.analyse_caller(None, channel="call").findings == ("hidden_number",)


def test_no_number_on_a_message_is_neutral():
    assert calls.analyse_caller(None, channel="sms").findings == ()


def test_parse_sender_from_chat_header_lines():
    text = "10:42\n+92 300 0000001\nonline\nAap ki pension release ho gayi hai"
    assert calls.find_number(text) == "+92 300 0000001"
    assert calls.find_number("no number here") is None
