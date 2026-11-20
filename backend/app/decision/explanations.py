"""Fixed citizen-facing explanations for each reason code.

No free text is generated for citizens: every sentence is written and reviewed
here, and has a matching pre-recorded Urdu audio clip (audio_key).
Urdu text must be reviewed by a native speaker before the demo.
"""
from app.schemas.contracts import Explanation, ReasonCode

_EXPLANATIONS: dict[ReasonCode, tuple[str, str, str]] = {
    # code: (urdu, english, icon)
    ReasonCode.APPROVED: (
        "آپ کا دعویٰ منظور ہو گیا ہے۔ پہلی ادائیگی جلد آپ کے اکاؤنٹ میں پہنچ جائے گی۔",
        "Your claim is approved. The first payment will reach your account soon.",
        "check",
    ),
    ReasonCode.DUPLICATE_CLAIM: (
        "اس پنشن کے لیے کسی اور نے بھی دعویٰ کیا ہے۔ ایک افسر تین دن میں جانچ کرے گا۔",
        "Another person has also claimed this pension. An officer will check within 3 days.",
        "people",
    ),
    ReasonCode.NAME_MISMATCH: (
        "آپ کے کاغذات پر نام ریکارڈ سے صاف طور پر نہیں ملتا۔ براہ کرم واضح تصویر بھیجیں یا مددگار کو اپنا شناختی کارڈ دکھائیں۔",
        "The name on your documents does not clearly match the records. "
        "Please send a clearer photo or show your CNIC to the helper.",
        "id-card",
    ),
    ReasonCode.MISSING_DEATH_CERT: (
        "ہمیں وفات کے سرٹیفکیٹ کی تصویر چاہیے۔",
        "We need a photo of the death certificate.",
        "document",
    ),
    ReasonCode.MISSING_INFO: (
        "کچھ معلومات کم ہیں۔ براہ کرم بتائی گئی چیز بھیجیں۔",
        "Some information is missing. Please send the item shown.",
        "question",
    ),
    ReasonCode.ACCOUNT_NOT_OWNED: (
        "یہ بینک اکاؤنٹ آپ کے نام پر نہیں ہے۔ براہ کرم اپنے نام کا اکاؤنٹ دیں۔",
        "This bank account is not in your name. Please give an account in your own name.",
        "bank",
    ),
    ReasonCode.ACCOUNT_REUSED: (
        "یہ اکاؤنٹ دوسرے دعووں میں بھی استعمال ہوا ہے۔ ایک افسر جانچ کرے گا۔",
        "This account is also used in other claims. An officer will check.",
        "bank-alert",
    ),
    ReasonCode.DOC_EDIT_RISK: (
        "آپ کے کاغذ کی مزید جانچ ضروری ہے۔ ایک افسر اسے دیکھے گا۔",
        "Your document needs more checking. An officer will look at it.",
        "document-alert",
    ),
    ReasonCode.NOT_ELIGIBLE: (
        "قواعد کے مطابق ایک افسر آپ کے دعوے کا جائزہ لے گا۔",
        "Under the rules, an officer will review your claim.",
        "rules",
    ),
    ReasonCode.JEV_UNDECIDED: (
        "ہمیں پورا یقین نہیں ہے، اس لیے ایک افسر آپ کا دعویٰ دیکھے گا۔",
        "We are not sure, so an officer will look at your claim.",
        "person",
    ),
    ReasonCode.LOW_CONFIDENCE: (
        "ہمیں پورا یقین نہیں ہے، اس لیے ایک افسر آپ کا دعویٰ دیکھے گا۔",
        "We are not sure, so an officer will look at your claim.",
        "person",
    ),
    ReasonCode.SERVICE_UNAVAILABLE: (
        "ہم ابھی سرکاری ریکارڈ تک نہیں پہنچ سکے۔ آپ کا دعویٰ محفوظ ہے اور ایک افسر اسے آگے بڑھائے گا۔",
        "We could not reach a government record right now. "
        "Your claim is saved and an officer will continue it.",
        "cloud-off",
    ),
}


def explain(code: ReasonCode) -> Explanation:
    text_ur, text_en, icon = _EXPLANATIONS[code]
    return Explanation(
        reason_code=code,
        text_ur=text_ur,
        text_en=text_en,
        audio_key=f"reason_{code.value.lower()}",
        icon=icon,
    )
