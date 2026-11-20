"""Phase 0 smoke test: does Jev separate scam from genuine messages in
English, Roman Urdu and Urdu script?

All messages below are invented for this test (no real people, numbers or links).
Run from backend/:  .venv/Scripts/python -m scripts.jev_smoke
Needs TYPESAFE_API_KEY in backend/.env. Writes results/jev_smoke.json.
"""
import json
import statistics
from pathlib import Path

from app.decision.jev_client import Band, JevClient, JevUnavailable, noul, noul_band

QUESTIONS = {
    "asks_fee": noul("Does the message ask the reader to pay a fee, charge or any money?"),
    "asks_secret": noul("Does the message ask for an OTP, PIN, password or verification code?"),
    "has_link": noul("Does the message contain a web link or ask the reader to open a website?"),
    "claims_government": noul("Does the message claim to come from a government office or programme?"),
    "urgency": noul("Does the message pressure the reader with a deadline, threat or prize?"),
}

# (language, is_scam, text)
MESSAGES: list[tuple[str, bool, str]] = [
    ("en", True, "Dear pensioner, your family pension of Rs 45,000 is released. Pay Rs 5000 processing fee within 24 hours at pension-release.example.com or it will be cancelled."),
    ("en", True, "Pension Office: verify your account now. Reply with the 6 digit code you just received to receive your payment today."),
    ("en", True, "Congratulations! You are selected for widow relief of Rs 25,000. Send Rs 1500 by mobile wallet to 0300-0000000 to unlock."),
    ("en", False, "Your survivor pension claim SP-1042 has been received. An officer will review it within 7 working days. No fee is charged."),
    ("en", False, "Reminder: please bring the original death certificate to the helper desk on Monday."),
    ("en", False, "Your claim SP-1042 is approved. The first payment will be credited to your registered account."),
    ("roman_ur", True, "Mohtarma aap ki pension release ho gayi hai, 3000 rupay fees jama karwain warna pension band ho jaye gi. Abhi link kholain: bit.example/pension"),
    ("roman_ur", True, "Pension daftar se: aap ke number par aya hua code humain bhejain takay payment aaj hi mil jaye."),
    ("roman_ur", True, "Mubarak ho! Bewa imdad program mein aap ka naam aa gaya hai. 2000 rupay bhej kar 25000 hasil karain, sirf aaj ki offer."),
    ("roman_ur", False, "Aap ki pension ki darkhwast mil gayi hai. Officer 7 din mein check karega. Koi fees nahi hai."),
    ("roman_ur", False, "Baraye meharbani wafat ka asal certificate peer ko helper desk par le aain."),
    ("roman_ur", False, "Aap ka claim manzoor ho gaya hai. Pehli adaigi aap ke account mein aa jaye gi."),
    ("roman_ur", False, "Ammi ki pension ka kya bana? Kal bank chalain ge InshaAllah."),
    ("ur", True, "محترمہ آپ کی پنشن جاری ہو گئی ہے۔ 24 گھنٹے میں 5000 روپے فیس جمع کروائیں ورنہ پنشن منسوخ ہو جائے گی۔"),
    ("ur", True, "پنشن دفتر: آپ کے فون پر آیا ہوا کوڈ ہمیں بھیجیں تاکہ آج ہی ادائیگی ہو سکے۔"),
    ("ur", True, "مبارک ہو! آپ بیوہ امداد کے لیے منتخب ہو گئی ہیں۔ 1500 روپے بھیج کر 25000 روپے حاصل کریں۔"),
    ("ur", False, "آپ کی پنشن کی درخواست موصول ہو گئی ہے۔ افسر سات دن میں جانچ کرے گا۔ کوئی فیس نہیں ہے۔"),
    ("ur", False, "پیر کے دن وفات کا اصل سرٹیفکیٹ مددگار ڈیسک پر لے آئیں۔"),
    ("ur", False, "آپ کا دعویٰ منظور ہو گیا ہے۔ پہلی ادائیگی آپ کے رجسٹرڈ اکاؤنٹ میں آ جائے گی۔"),
    ("ur", False, "کل بینک چلیں گے ان شاء اللہ، امی کی پنشن کا پتہ کرنا ہے۔"),
]

SCAM_SIGNALS = ("asks_fee", "asks_secret", "has_link")


def scam_score(nouls: dict[str, float]) -> float:
    """Simple combination for the smoke test only: strongest scam signal."""
    return max(nouls[name] for name in SCAM_SIGNALS)


def summarise(rows: list[dict]) -> dict:
    summary = {}
    for language in ("en", "roman_ur", "ur"):
        subset = [r for r in rows if r["language"] == language]
        scams = [r for r in subset if r["is_scam"]]
        genuine = [r for r in subset if not r["is_scam"]]
        summary[language] = {
            "n": len(subset),
            "missed_scams": sum(1 for r in scams if r["band"] != Band.YES.value),
            "false_alarms": sum(1 for r in genuine if r["band"] == Band.YES.value),
            "undecided": sum(1 for r in subset if r["band"] == Band.UNDECIDED.value),
            "mean_score_scam": round(statistics.mean(r["scam_score"] for r in scams), 3) if scams else None,
            "mean_score_genuine": round(statistics.mean(r["scam_score"] for r in genuine), 3) if genuine else None,
        }
    return summary


def main() -> None:
    client = JevClient()
    rows = []
    try:
        for language, is_scam, text in MESSAGES:
            try:
                result = client.ask(text, QUESTIONS)
            except JevUnavailable as exc:
                print(f"[{language}] Jev unavailable: {exc}")
                continue
            nouls = {name: result.noul(name) for name in QUESTIONS}
            score = scam_score(nouls)
            band = noul_band(score).value
            rows.append(
                {
                    "language": language,
                    "is_scam": is_scam,
                    "model": result.model,
                    "latency_ms": result.latency_ms,
                    "nouls": nouls,
                    "scam_score": score,
                    "band": band,
                }
            )
            print(f"[{language:8}] scam={is_scam!s:5} score={score:.2f} band={band:9} {result.latency_ms}ms model={result.model}")
    finally:
        client.close()

    if not rows:
        print("No answers. Check TYPESAFE_API_KEY and network.")
        return

    report = {
        "models_seen": sorted({r["model"] for r in rows}),
        "median_latency_ms": statistics.median(r["latency_ms"] for r in rows),
        "summary": summarise(rows),
        "rows": rows,
    }
    out = Path("results/jev_smoke.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
