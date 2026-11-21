"""Generate MOCK / SPECIMEN document images for the demo personas.

    python scripts/make_mock_docs.py            # writes backend/sample_docs/

Follows docs/research/round2.md section 1 (field order from public sources,
layout is our own design). Every image carries a "MOCK / SPECIMEN" banner and a
diagonal watermark, and "MOCK" in its metadata. No logo, emblem, guilloche,
hologram or government header is drawn. All people, numbers and offices are
invented (mock CNICs start with 90000).

Outputs per document: original PNG, a WhatsApp-style recompressed JPEG and a
phone-screenshot PNG. One death certificate is edited in the date and name
region (plus a pasted seal) for the "needs a second look" edit-risk demo;
manifest.json records the edited boxes as ground truth.
"""
import hashlib
import io
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

OUT_DIR = Path(__file__).resolve().parent.parent / "sample_docs"
MOCK_TEXT = "MOCK / SPECIMEN"
BANNER = "MOCK / SPECIMEN - NOT A REAL DOCUMENT - SAHARA PROTOTYPE"
PAPER, INK, FAINT, RED = (250, 248, 240), (25, 25, 35), (120, 120, 130), (200, 30, 30)
CARD_SIZE, A4_SIZE = (1012, 638), (1240, 1754)
WHATSAPP_MAX_SIDE, WHATSAPP_QUALITY = 1600, 50
SCREENSHOT_SIZE, SCREENSHOT_SCALE = (1080, 2340), 0.8

ZAINAB = {"name": "Zainab Bibi", "father": "Ghulam Rasool", "cnic": "90000-0000002-2", "dob": "01.06.1962", "gender": "F",
          "address": "House 12-B, Street 4, Gulshan (mock), Karachi"}
ASLAM = {"name": "Muhammad Aslam", "father": "Ghulam Nabi", "cnic": "90000-0000001-1", "dob": "10.03.1955", "gender": "M",
         "address": "House 12-B, Street 4, Gulshan (mock), Karachi"}
DEATH = {"cert_no": "DC-UC12-2026-0412", "uc": "UC-12 Gulshan (mock)", "name": "Mohd. Aslam", "date": "14.08.2026",
         "place": "Home, Gulshan (mock), Karachi", "cause": "Natural causes (mock)", "graveyard": "Mock Graveyard, Block 7"}
TAMPERED_DATE, TAMPERED_NAME = "14.06.2026", "Mohd. Akram"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    names = ("DejaVuSans-Bold.ttf", "arialbd.ttf") if bold else ("DejaVuSans.ttf", "arial.ttf")
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def banner(img: Image.Image, height: int) -> None:
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, img.width, height), fill=RED)
    size = int(height * 0.42)
    while draw.textlength(BANNER, font=font(size, bold=True)) > img.width - 40 and size > 10:
        size -= 1  # shrink to fit narrow cards
    f = font(size, bold=True)
    w = draw.textlength(BANNER, font=f)
    draw.text(((img.width - w) / 2, height * 0.25), BANNER, fill="white", font=f)


def watermark(img: Image.Image) -> Image.Image:
    """Diagonal repeated MOCK / SPECIMEN, red at ~35% opacity."""
    side = int((img.width ** 2 + img.height ** 2) ** 0.5)
    layer = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    f = font(max(img.width // 14, 28), bold=True)
    step_x, step_y = int(draw.textlength(MOCK_TEXT, font=f) * 1.4), f.size * 4
    for row, y in enumerate(range(0, side, step_y)):
        for x in range(-step_x + (row % 2) * step_x // 2, side, step_x):
            draw.text((x, y), MOCK_TEXT, fill=(*RED, 90), font=f)
    layer = layer.rotate(30, resample=Image.BICUBIC)
    left, top = (side - img.width) // 2, (side - img.height) // 2
    layer = layer.crop((left, top, left + img.width, top + img.height))
    return Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB")


def seal(text: str, size: int = 190) -> Image.Image:
    """A round MOCK SEAL on its own transparent layer (so tamper variants can copy it)."""
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    color = (40, 60, 160, 200)
    draw.ellipse((4, 4, size - 4, size - 4), outline=color, width=6)
    draw.ellipse((22, 22, size - 22, size - 22), outline=color, width=2)
    for i, line in enumerate(("MOCK SEAL", text, "NOT REAL")):
        f = font(20 if i != 1 else 16, bold=i == 0)
        w = draw.textlength(line, font=f)
        draw.text(((size - w) / 2, size / 2 - 34 + i * 26), line, fill=color, font=f)
    return layer


def fake_qr(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], payload: str) -> None:
    """A QR-like pattern from a hash of the payload. Deliberately not a scannable code."""
    x0, y0, x1, y1 = box
    cells = 25
    cell = (x1 - x0) // cells
    rng = random.Random(hashlib.sha256(payload.encode()).hexdigest())
    draw.rectangle(box, fill="white")
    for r in range(cells):
        for c in range(cells):
            if rng.random() < 0.45:
                draw.rectangle((x0 + c * cell, y0 + r * cell, x0 + (c + 1) * cell - 1, y0 + (r + 1) * cell - 1), fill=INK)
    draw.text((x0, y1 + 6), "QR (MOCK, NOT SCANNABLE)", fill=FAINT, font=font(14))


def field(draw: ImageDraw.ImageDraw, xy: tuple[int, int], label: str, value: str, size: int = 30) -> None:
    draw.text(xy, label, fill=FAINT, font=font(int(size * 0.55)))
    draw.text((xy[0], xy[1] + int(size * 0.7)), value, fill=INK, font=font(size, bold=True))


def silhouette(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(205, 205, 210), outline=FAINT, width=2)
    cx, w, h = (x0 + x1) // 2, x1 - x0, y1 - y0
    draw.ellipse((cx - w * 0.2, y0 + h * 0.15, cx + w * 0.2, y0 + h * 0.5), fill=(160, 160, 168))
    draw.ellipse((cx - w * 0.38, y0 + h * 0.55, cx + w * 0.38, y1 + h * 0.3), fill=(160, 160, 168))
    draw.rectangle((x0, y1, x1, y1 + h), fill=PAPER)  # clip the body ellipse
    draw.rectangle(box, outline=FAINT, width=2)


def cnic_front(p: dict) -> Image.Image:
    img = Image.new("RGB", CARD_SIZE, (232, 242, 236))
    banner(img, 80)
    d = ImageDraw.Draw(img)
    field(d, (40, 110), "Name", p["name"].upper())
    field(d, (40, 200), "Father / Husband Name", p["father"].upper())
    field(d, (40, 300), "Gender", p["gender"], 26)
    field(d, (220, 300), "Country of Stay", "Pakistan", 26)
    field(d, (40, 380), "Identity Number", p["cnic"], 28)
    field(d, (420, 380), "Date of Birth", p["dob"], 28)
    field(d, (40, 450), "Date of Issue", "01.01.2020", 24)
    field(d, (300, 450), "Date of Expiry", "Lifetime" if int(p["dob"][-4:]) <= 1966 else "01.01.2030", 24)
    silhouette(d, (700, 110, 970, 430))
    d.text((700, 450), "Holder's Signature", fill=FAINT, font=font(16))
    d.line([(710, 510), (760, 480), (800, 515), (850, 485), (930, 505)], fill=INK, width=3)
    d.rectangle((560, 520, 660, 600), fill=(185, 185, 190), outline=FAINT)
    d.text((570, 550), "CHIP (MOCK)", fill=INK, font=font(14))
    return watermark(img)


def cnic_back(p: dict) -> Image.Image:
    img = Image.new("RGB", CARD_SIZE, (232, 242, 236))
    banner(img, 50)
    d = ImageDraw.Draw(img)
    field(d, (40, 70), "Present Address", p["address"], 22)
    field(d, (40, 220), "Permanent Address", p["address"], 22)
    fake_qr(d, (760, 70, 960, 270), f"MOCK|{p['cnic']}|NOT REAL")
    field(d, (40, 400), "Identity Number", p["cnic"], 26)
    d.text((40, 570), "Serial MOCK-000123", fill=FAINT, font=font(22))
    return watermark(img)


def _a4(title: str, number: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", A4_SIZE, PAPER)
    banner(img, 70)
    d = ImageDraw.Draw(img)
    f = font(44, bold=True)
    d.text(((A4_SIZE[0] - d.textlength(title, font=f)) / 2, 100), title, fill=INK, font=f)
    d.text((A4_SIZE[0] - 60 - d.textlength(number, font=font(24)), 180), number, fill=INK, font=font(24))
    return img, d


def frc() -> Image.Image:
    img, d = _a4("FAMILY REGISTRATION CERTIFICATE (MOCK)", "No. MOCK-FRC-1001")
    field(d, (60, 200), "Type", "By Marriage", 26)
    field(d, (60, 270), "Applicant", f"{ZAINAB['name']}   CNIC {ZAINAB['cnic']}", 26)
    d.text((880, 220), "Issued 20.08.2026", fill=INK, font=font(22))
    cols = ((60, "Sr"), (120, "Name"), (470, "Relation"), (650, "CNIC"), (930, "DOB"), (1080, "Status"))
    rows = (("1", ASLAM["name"], "Husband", ASLAM["cnic"], ASLAM["dob"], "Deceased"),
            ("2", ZAINAB["name"], "Self (Wife)", ZAINAB["cnic"], ZAINAB["dob"], "Alive"),
            ("3", "Imran Aslam", "Son", "90000-0000002-3", "14.02.1986", "Alive"),
            ("4", "Nadia Aslam", "Daughter", "90000-0000002-4", "30.09.1989", "Alive"))
    y = 400
    d.rectangle((50, y - 10, 1190, y + 40), fill=(225, 225, 215))
    for x, head in cols:
        d.text((x, y), head, fill=INK, font=font(22, bold=True))
    for row in rows:
        y += 70
        d.line([(50, y - 15), (1190, y - 15)], fill=FAINT)
        for (x, _), value in zip(cols, row):
            d.text((x, y), value, fill=INK, font=font(21))
    img.paste(s := seal("FRC MOCK"), (120, 1350), s)
    fake_qr(d, (900, 1350, 1100, 1550), "MOCK|FRC-1001|NOT REAL")
    return watermark(img)


DEATH_DATE_BOX, DEATH_NAME_BOX = (58, 468, 700, 510), (58, 258, 900, 300)  # value areas only


def death_certificate(date_text: str = DEATH["date"], name_text: str = DEATH["name"]) -> Image.Image:
    img, d = _a4("DEATH CERTIFICATE (MOCK)", f"Reg. No. {DEATH['cert_no']}")
    field(d, (60, 160), "Union Council", DEATH["uc"], 26)
    field(d, (60, 240), "Name of Deceased", name_text)
    field(d, (60, 320), "Father / Husband Name", ASLAM["father"])
    field(d, (60, 380), "Deceased CNIC", ASLAM["cnic"], 26)
    field(d, (700, 380), "Gender", "Male", 26)
    field(d, (60, 450), "Date of Death", date_text)
    field(d, (60, 520), "Place of Death", DEATH["place"], 26)
    field(d, (60, 590), "Cause of Death", DEATH["cause"], 26)
    field(d, (60, 660), "Graveyard", DEATH["graveyard"], 26)
    field(d, (60, 760), "Informant", f"{ZAINAB['name']} (Wife)   CNIC {ZAINAB['cnic']}", 26)
    field(d, (60, 860), "Date of Registration", "18.08.2026", 26)
    field(d, (60, 930), "Date of Issue", "19.08.2026", 26)
    d.text((60, 1500), "Secretary, Union Council (MOCK)", fill=INK, font=font(22))
    d.line([(70, 1480), (130, 1450), (190, 1485), (260, 1455)], fill=INK, width=3)
    img.paste(s := seal("UC-12 MOCK"), (360, 1380), s)
    return watermark(img)


def tamper(original: Image.Image) -> tuple[Image.Image, list[dict]]:
    """Paint over the date and name, retype them a little off, and paste a second copy of the seal."""
    img = original.copy()
    d = ImageDraw.Draw(img)
    edits = []
    for box, label, value in ((DEATH_DATE_BOX, "date_of_death", TAMPERED_DATE), (DEATH_NAME_BOX, "name_of_deceased", TAMPERED_NAME)):
        d.rectangle(box, fill=(247, 246, 236))  # flat patch: the watermark under it is gone
        d.text((box[0] + 4, box[1] + 2), value, fill=(35, 30, 30), font=font(31, bold=True))
        edits.append({"field": label, "box": list(box), "new_value": value})
    s = seal("UC-12 MOCK")
    img.paste(s, (760, 1380), s)
    edits.append({"field": "seal_copy_move", "box": [760, 1380, 760 + s.width, 1380 + s.height]})
    return img, edits


def nikah_nama() -> Image.Image:
    img, d = _a4("NIKAH NAMA (MOCK, widow subset of Form II)", "Leaf MOCK-NR-07 / 23")
    rows = (("1", "Place of marriage", "Gulshan (mock), Karachi"),
            ("2", "Groom, father, residence", f"{ASLAM['name']} s/o {ASLAM['father']}, Karachi"),
            ("3", "Groom age", "28"),
            ("4", "Bride, father, residence", f"{ZAINAB['name']} d/o {ZAINAB['father']}, Karachi"),
            ("5", "Maiden / widow / divorcee", "Maiden"),
            ("6", "Bride age", "21"),
            ("11", "Witnesses", "Mock Witness One; Mock Witness Two"),
            ("12", "Date of marriage", "12.03.1983"),
            ("13-15", "Dower", "Rs 0 (MOCK)"),
            ("23", "Solemnised by", "Mock Nikah Khwan"),
            ("24", "Date of registration", "15.03.1983"),
            ("25", "Fee", "Rs 0 (MOCK)"))
    y = 220
    for col, label, value in rows:
        d.line([(50, y - 12), (1190, y - 12)], fill=FAINT)
        d.text((60, y), col, fill=FAINT, font=font(22))
        d.text((150, y), label, fill=FAINT, font=font(22))
        d.text((560, y), value, fill=INK, font=font(23, bold=True))
        y += 75
    d.text((60, y + 40), "Groom ______    Bride ______    Registrar ______", fill=INK, font=font(24))
    img.paste(s := seal("NIKAH REG MOCK"), (900, y + 120), s)
    return watermark(img)


def _png_info(doc: str) -> PngInfo:
    info = PngInfo()
    info.add_text("MOCK", "true")
    info.add_text("Description", f"{MOCK_TEXT}: {doc}. Synthetic Sahara prototype document, not a real record.")
    return info


def save_png(img: Image.Image, path: Path, doc: str) -> None:
    img.save(path, "PNG", pnginfo=_png_info(doc), optimize=True)


def whatsapp(img: Image.Image, path: Path, doc: str) -> None:
    scale = min(1.0, WHATSAPP_MAX_SIDE / max(img.size))
    small = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS) if scale < 1 else img
    first = io.BytesIO()
    small.save(first, "JPEG", quality=80)
    again = Image.open(io.BytesIO(first.getvalue()))  # recompressed twice, as when forwarded
    exif = Image.Exif()
    exif[0x010E] = f"{MOCK_TEXT}: {doc}"  # ImageDescription
    again.save(path, "JPEG", quality=WHATSAPP_QUALITY, exif=exif, comment=f"MOCK {doc}".encode())


def screenshot(img: Image.Image, path: Path, doc: str) -> None:
    canvas = Image.new("RGB", SCREENSHOT_SIZE, (18, 18, 20))
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, 0, SCREENSHOT_SIZE[0], 90), fill=(30, 30, 34))
    d.text((40, 28), "12:41", fill="white", font=font(32))
    d.text((820, 28), "4G  62%", fill="white", font=font(32))
    width = int(SCREENSHOT_SIZE[0] * SCREENSHOT_SCALE)
    shown = img.resize((width, int(img.height * width / img.width)), Image.BILINEAR)
    canvas.paste(shown, ((SCREENSHOT_SIZE[0] - width) // 2, max(140, (SCREENSHOT_SIZE[1] - shown.height) // 2)))
    save_png(canvas, path, doc)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    docs = {
        "cnic_front_zainab": (cnic_front(ZAINAB), "CNIC front, Zainab Bibi (claimant)"),
        "cnic_back_zainab": (cnic_back(ZAINAB), "CNIC back, Zainab Bibi"),
        "cnic_front_aslam": (cnic_front(ASLAM), "CNIC front, Muhammad Aslam (deceased)"),
        "frc_aslam_family": (frc(), "Family registration certificate FRC-1001"),
        "death_certificate_aslam": (death_certificate(), "Death certificate DC-UC12-2026-0412 (name printed as Mohd. Aslam)"),
        "nikah_nama_aslam_zainab": (nikah_nama(), "Nikah nama, Muhammad Aslam and Zainab Bibi"),
    }
    manifest = {"note": BANNER, "files": []}
    for key, (img, desc) in docs.items():
        for suffix, writer in (("png", save_png), ("whatsapp.jpg", whatsapp), ("screenshot.png", screenshot)):
            name = f"{key}.{suffix}"
            writer(img, OUT_DIR / name, desc)
            manifest["files"].append({"file": name, "doc": key, "variant": suffix.split(".")[0] if "." in suffix else "original",
                                      "description": desc, "edited": False})
    edited, edits = tamper(docs["death_certificate_aslam"][0])
    for name, writer in (("death_certificate_aslam_edited.png", save_png), ("death_certificate_aslam_edited.whatsapp.jpg", whatsapp)):
        writer(edited, OUT_DIR / name, "Death certificate, EDITED copy for the edit-risk demo")
        manifest["files"].append({"file": name, "doc": "death_certificate_aslam", "variant": "edited",
                                  "description": "Date and name region repainted, seal pasted twice (needs a second look)",
                                  "edited": True, "edits": edits})
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    total = sum(f.stat().st_size for f in OUT_DIR.iterdir())
    print(f"wrote {len(manifest['files'])} images to {OUT_DIR} ({total / 1e6:.2f} MB)")  # noqa: T201 - CLI output


if __name__ == "__main__":
    main()
