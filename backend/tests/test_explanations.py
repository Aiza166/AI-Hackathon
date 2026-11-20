from app.decision.explanations import explain
from app.schemas.contracts import ReasonCode


def test_every_reason_code_has_urdu_english_audio_and_icon():
    for code in ReasonCode:
        explanation = explain(code)
        assert explanation.text_ur.strip()
        assert explanation.text_en.strip()
        assert explanation.icon
        assert explanation.audio_key == f"reason_{code.value.lower()}"


def test_urdu_text_is_actually_urdu_script():
    for code in ReasonCode:
        text = explain(code).text_ur
        assert any("؀" <= ch <= "ۿ" for ch in text), code
