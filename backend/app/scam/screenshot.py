"""Turn OCR lines from a chat screenshot (WhatsApp, SMS app) into message text and a sender number.

Phone status-bar and chat-chrome lines (clock, battery, "online", "typing...", day
separators) are dropped. The first phone number seen is taken as the sender, because a
chat header shows the number of an unsaved contact. The citizen sees what was read.
"""
import re

from app.documents.ocr import OcrResult
from app.scam.calls import find_number

MAX_TEXT = 2000
CHROME = re.compile(
    r"^(\d{1,2}[:.]\d{2}(\s*[ap]\.?m\.?)?|\d{1,3}\s*%|(4g|5g|lte|volte|wifi)(\s+\d{1,3}\s*%)?\s*|online|typing\.*|"
    r"today|yesterday|aaj|kal|last seen.*|tap here for contact info|messages and calls are end-to-end encrypted.*|"
    r"آن لائن|ٹائپ کر رہا ہے.*|آج|کل)$",
    re.I,
)


def chat_text(ocr: OcrResult) -> tuple[str, str | None]:
    kept = [line.text.strip() for line in ocr.lines if line.text.strip() and not CHROME.match(line.text.strip())]
    text = "\n".join(kept)[:MAX_TEXT]
    return text, find_number(text)
