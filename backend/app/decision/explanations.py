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
    ReasonCode.NOT_IN_FAMILY_RECORD: (
        "خاندانی ریکارڈ میں آپ کا نام مرحوم کے ساتھ نہیں ملا۔ ایک افسر جانچ کرے گا۔",
        "Your name was not found with the deceased in the family record. An officer will check.",
        "family",
    ),
    ReasonCode.DEATH_NOT_VERIFIED: (
        "وفات کا ریکارڈ ابھی تصدیق نہیں ہو سکا۔ ایک افسر جانچ کرے گا۔",
        "The death record could not be confirmed yet. An officer will check.",
        "document-alert",
    ),
    ReasonCode.NO_PENSION_RECORD: (
        "مرحوم کی پنشن کا ریکارڈ نہیں ملا۔ ایک افسر جانچ کرے گا۔",
        "No pension record was found for the deceased. An officer will check.",
        "rules",
    ),
    ReasonCode.ALREADY_DRAWING: (
        "ریکارڈ کے مطابق آپ پہلے سے ایک خاندانی پنشن لے رہی ہیں۔ ایک افسر جانچ کرے گا۔",
        "The records show you already receive a family pension. An officer will check.",
        "rules",
    ),
    ReasonCode.CHILD_OVER_AGE: (
        "قواعد کے مطابق اس عمر کے بیٹے کے لیے ایک افسر دعوے کا جائزہ لے گا۔",
        "Under the rules, an officer will review a claim from a son of this age.",
        "rules",
    ),
    ReasonCode.DAUGHTER_MARRIED: (
        "قواعد کے مطابق ایک افسر بیٹی کے دعوے کا جائزہ لے گا۔",
        "Under the rules, an officer will review this daughter's claim.",
        "rules",
    ),
    ReasonCode.WIDOW_FIRST: (
        "قواعد کے مطابق پہلے بیوہ کا حق ہے۔ ایک افسر جائزہ لے گا۔",
        "Under the rules, the widow comes first. An officer will review.",
        "rules",
    ),
    ReasonCode.PAYEE_CLOSE_MATCH: (
        "بینک اکاؤنٹ کا نام آپ کے نام سے پوری طرح نہیں ملتا۔ براہ کرم اکاؤنٹ کی تصدیق کریں۔",
        "The bank account name does not fully match your name. Please confirm the account.",
        "bank",
    ),
    ReasonCode.TIME_LIMITED: (
        "آپ کا دعویٰ منظور ہے، لیکن نئے قاعدے کے مطابق یہ پنشن ایک مقررہ مدت تک ملے گی۔",
        "Your claim is approved, but under the new rule this pension is paid for a fixed period.",
        "calendar",
    ),
    ReasonCode.MULTIPLE_CANDIDATES: (
        "ریکارڈ میں اس نام کے ایک سے زیادہ لوگ ہیں۔ براہ کرم مرحوم کا شناختی کارڈ نمبر دیں۔",
        "More than one person with this name is in the records. Please give the deceased's CNIC number.",
        "id-card",
    ),
    ReasonCode.CONFIRM_DOB: (
        "براہ کرم اپنی تاریخ پیدائش کی تصدیق کریں۔ یہ آپ کے شناختی کارڈ پر لکھی ہے۔",
        "Please confirm your date of birth. It is printed on your CNIC.",
        "calendar",
    ),
    ReasonCode.DOB_MISMATCH: (
        "آپ کی بتائی ہوئی تاریخ پیدائش ریکارڈ سے نہیں ملتی۔ اپنے شناختی کارڈ سے دیکھ کر دوبارہ بتائیں، یا مددگار کو کارڈ دکھائیں۔",
        "The date of birth you gave does not match the records. "
        "Check it on your CNIC and give it again, or show your CNIC to the helper.",
        "calendar",
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
