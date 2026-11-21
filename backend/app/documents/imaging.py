"""Load an uploaded photo safely and check whether it is good enough to read.

Every later step (OCR, forensics, Jev) works on the image returned by load():
upright (EXIF orientation applied), RGB, longest side at most MAX_SIDE.
"""
import hashlib
import io
from dataclasses import asdict, dataclass

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE = 1568  # Jev limit and plenty for OCR of an A4 page or an ID card
MIN_SIDE = 280  # Jev minimum; smaller photos are too small to read anyway
MAX_PIXELS = 40_000_000  # decompression-bomb guard (a 12 MP phone photo is ~12 M)
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
# Pillow raises DecompressionBombError above 2x this and only warns between 1x and 2x,
# so load() also checks the pixel count itself before decoding anything.
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
_MAGIC_JPEG = bytes([0xFF, 0xD8, 0xFF])
_MAGIC_PNG = bytes([0x89]) + b"PNG" + bytes([0x0D, 0x0A, 0x1A, 0x0A])


def sniff_format(data: bytes) -> str | None:
    """Image type from the file's magic bytes (never from the name or the declared type)."""
    if data.startswith(_MAGIC_JPEG):
        return "JPEG"
    if data.startswith(_MAGIC_PNG):
        return "PNG"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "WEBP"
    return None

# Quality thresholds, tuned on backend/sample_docs (all pass) and on blurred/darkened copies (all fail).
BLUR_MIN_VARIANCE = 60.0  # variance of the Laplacian on a 1000 px wide grey copy
DARK_MAX_P90 = 90.0  # 90th-percentile brightness: a dark photo has no bright paper at all
# (a percentile, not the mean, so a screenshot with black phone borders is not "too dark")
BRIGHT_MIN_MEAN = 250.0  # almost white: overexposed or blank
LOW_CONTRAST_STD = 12.0


class BadImage(ValueError):
    """The upload is not an image we accept (wrong format, corrupt, or absurdly large)."""


@dataclass(frozen=True)
class Quality:
    ok: bool
    problems: tuple[str, ...]  # too_small | blurry | too_dark | too_bright | low_contrast
    blur_variance: float
    brightness: float
    width: int
    height: int

    def to_dict(self) -> dict:
        return {**asdict(self), "problems": list(self.problems)}


@dataclass(frozen=True)
class LoadedImage:
    image: Image.Image  # upright RGB, longest side <= MAX_SIDE
    original_format: str
    original_size: tuple[int, int]
    sha256: str  # of the uploaded bytes
    exif: dict  # a few informational tags only


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


_EXIF_TAGS = {0x0110: "camera_model", 0x010F: "camera_make", 0x0131: "software", 0x0132: "datetime"}


def _exif_summary(img: Image.Image) -> dict:
    try:
        exif = img.getexif()
    except Exception:  # noqa: BLE001 - broken EXIF is common and never counts against anyone
        return {}
    out = {}
    for tag, name in _EXIF_TAGS.items():
        value = exif.get(tag)
        if isinstance(value, bytes):
            value = value.decode("utf-8", "replace")
        if value:
            out[name] = str(value)[:80]
    return out


def load(data: bytes) -> LoadedImage:
    sniffed = sniff_format(data)
    if sniffed is None:
        raise BadImage("Only JPEG, PNG or WebP photos are accepted")
    try:
        img = Image.open(io.BytesIO(data))  # lazy: reads the header only
        fmt = (img.format or "").upper()
        if fmt not in ALLOWED_FORMATS or fmt != sniffed:
            raise BadImage("Only JPEG, PNG or WebP photos are accepted")
        if img.width * img.height > MAX_PIXELS:
            raise BadImage("The photo has too many pixels")
        exif = _exif_summary(img)
        img = ImageOps.exif_transpose(img)
        original_size = img.size
        img = img.convert("RGB")
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise BadImage("The file is not a readable photo") from exc
    if max(img.size) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    return LoadedImage(image=img, original_format=fmt, original_size=original_size, sha256=sha256_hex(data), exif=exif)


def to_gray(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("L"))


def to_bgr(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def check_quality(loaded: LoadedImage) -> Quality:
    width, height = loaded.original_size
    gray = to_gray(loaded.image)
    # Measure sharpness at a fixed scale so a big photo and a small one compare fairly.
    scale = 1000 / gray.shape[1]
    norm = cv2.resize(gray, (1000, max(1, int(gray.shape[0] * scale))), interpolation=cv2.INTER_AREA)
    blur = float(cv2.Laplacian(norm, cv2.CV_64F).var())
    brightness = float(norm.mean())
    bright_p90 = float(np.percentile(norm, 90))
    contrast = float(norm.std())
    problems = []
    if min(width, height) < MIN_SIDE:
        problems.append("too_small")
    if blur < BLUR_MIN_VARIANCE:
        problems.append("blurry")
    if bright_p90 < DARK_MAX_P90:
        problems.append("too_dark")
    elif brightness > BRIGHT_MIN_MEAN:
        problems.append("too_bright")
    if contrast < LOW_CONTRAST_STD:
        problems.append("low_contrast")
    return Quality(ok=not problems, problems=tuple(problems), blur_variance=round(blur, 1),
                   brightness=round(brightness, 1), width=width, height=height)


def jpeg_bytes(img: Image.Image, quality: int = 85) -> bytes:
    """Re-encode as a fresh baseline JPEG. No exif/icc/xmp is passed, so the stored copy
    carries no EXIF (GPS, camera serial, timestamps) from the citizen's phone."""
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=quality, optimize=True)  # baseline JPEG (Jev rejects progressive)
    return buf.getvalue()
