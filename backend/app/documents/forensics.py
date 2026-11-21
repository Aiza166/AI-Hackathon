"""Image forensics: indicators for an officer, never a verdict.

1. Copy-move on stamp/seal regions: find coloured, roughly round or square ink blobs
   (stamps, seals) and compare every similar-sized pair. Two impressions of a hand
   stamp always differ (angle, ink, pressure); two that are nearly pixel-identical
   mean one was pasted. ORB keypoint matches between the pair are kept as evidence.
   Restricting the check to stamp regions matters: printed text repeats the same
   glyphs everywhere, so a whole-page self-match flags every clean document.
2. ELA (error level analysis): recompress at JPEG quality 90 and show the difference
   as a heatmap next to the image. Informational only: WhatsApp recompression,
   screenshots and flat backgrounds all change ELA, so it never raises risk alone.
3. EXIF: context only. Missing EXIF never counts against anyone.

Tuned on backend/sample_docs: the edited death certificate (seal pasted twice) is
flagged in both PNG and WhatsApp JPEG form; no original, WhatsApp or screenshot
variant of the clean documents is flagged.
"""
import io
from dataclasses import asdict, dataclass, field

import cv2
import numpy as np
from PIL import Image, ImageChops, ImageOps

from app.documents.imaging import to_bgr, to_gray

# Stamp candidates: saturated ink (any hue), closed into blobs.
INK_MIN_SATURATION = 90
INK_MAX_VALUE = 230
INK_MIN_VALUE = 100  # very dark saturated pixels are black print under a coloured overlay, not stamp ink
HUE_BINS = 6  # stamps are compared within one ink colour, so a blue seal never merges with red print
CLOSE_KERNEL = 15
STAMP_MIN_SIDE, STAMP_MAX_SIDE = 50, 600
STAMP_MAX_ASPECT = 2.0
SIZE_TOLERANCE = 0.3  # a paste may be scaled 0.8-1.25x and rotated, which grows its box
SEARCH_PAD = 30
# Normalised cross-correlation of the two ink masks. Sample docs: pasted copy 0.81-0.86,
# every other pair <= 0.0. Real double hand-stamping lands far below 0.6.
COPY_MOVE_NCC = 0.6
MIN_STAMP_DISTANCE = 40
# A paste can be rotated or rescaled to dodge a plain template match (red team M1: 3 degrees
# dropped NCC to 0.59). The template is also tried at these angles and scales; a genuine
# second impression is still inked and pressed differently, so its best score stays low.
SEARCH_ANGLES = tuple(range(-12, 13, 2))
SEARCH_SCALES = (0.8, 0.85, 0.9, 0.95, 1.0, 1.05, 1.1, 1.17, 1.25)
_SEARCH_ORDER = sorted(((a, sc) for a in SEARCH_ANGLES for sc in SEARCH_SCALES), key=lambda t: abs(t[0]) + 20 * abs(t[1] - 1))
CLEAR_COPY_NCC = 0.75

ELA_QUALITY = 90
ELA_GAIN = 12


@dataclass(frozen=True)
class CopyMove:
    found: bool
    score: float  # best NCC between two stamp candidates
    regions: list = field(default_factory=list)  # [[x0,y0,x1,y1], [x0,y0,x1,y1]] in analysed-image pixels
    orb_matches: int = 0
    stamp_candidates: int = 0


@dataclass(frozen=True)
class ForensicReport:
    copy_move: CopyMove
    ela_mean: float
    ela_p99: float
    exif: dict
    looks_like_screenshot: bool

    def to_dict(self) -> dict:
        return asdict(self)


def _ink_masks(bgr: np.ndarray) -> list[np.ndarray]:
    """One mask of saturated ink per hue family (OpenCV hue is 0-179; shifted so red is one bin)."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    ink = (hsv[..., 1] > INK_MIN_SATURATION) & (hsv[..., 2] < INK_MAX_VALUE) & (hsv[..., 2] >= INK_MIN_VALUE)
    width = 180 // HUE_BINS
    hue_bin = ((hsv[..., 0].astype(np.int32) + width // 2) % 180) // width
    return [((ink & (hue_bin == b)).astype(np.uint8) * 255) for b in range(HUE_BINS)]


def stamp_candidates(mask: np.ndarray) -> list[tuple[int, int, int, int]]:
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (CLOSE_KERNEL, CLOSE_KERNEL))
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    count, _, stats, _ = cv2.connectedComponentsWithStats(closed)
    boxes = []
    for i in range(1, count):
        x, y, w, h, _ = (int(v) for v in stats[i])
        if not (STAMP_MIN_SIDE <= w <= STAMP_MAX_SIDE and STAMP_MIN_SIDE <= h <= STAMP_MAX_SIDE):
            continue
        if max(w / h, h / w) > STAMP_MAX_ASPECT:
            continue
        boxes.append((x, y, w, h))
    return boxes


def _similar_size(a: tuple, b: tuple) -> bool:
    return abs(a[2] - b[2]) <= SIZE_TOLERANCE * max(a[2], b[2]) and abs(a[3] - b[3]) <= SIZE_TOLERANCE * max(a[3], b[3])


def _ncc_one_way(mask: np.ndarray, a: tuple, b: tuple) -> float:
    """Slide the core of stamp a (10% margin trimmed) over stamp b plus a search margin."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    mx, my = aw // 10, ah // 10
    template = mask[ay + my:ay + ah - my, ax + mx:ax + aw - mx].astype(np.float32)
    region = mask[max(0, by - SEARCH_PAD):by + bh + SEARCH_PAD, max(0, bx - SEARCH_PAD):bx + bw + SEARCH_PAD].astype(np.float32)
    if template.shape[0] > region.shape[0] or template.shape[1] > region.shape[1]:
        return 0.0
    if template.std() == 0 or region.std() == 0:
        return 0.0
    best = 0.0
    for angle, scale in _SEARCH_ORDER:
        warped = _warp(template, angle, scale)
        if warped.shape[0] > region.shape[0] or warped.shape[1] > region.shape[1] or warped.std() == 0:
            continue
        best = max(best, float(cv2.matchTemplate(region, warped, cv2.TM_CCOEFF_NORMED).max()))
        if best >= CLEAR_COPY_NCC:
            break  # clearly a copy: no need to search further
    return best


def _warp(template: np.ndarray, angle: float, scale: float) -> np.ndarray:
    """Rotate and scale the ink mask about its centre into a canvas that holds all of it."""
    if angle == 0 and scale == 1.0:
        return template
    h, w = template.shape
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, scale)
    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_w, new_h = int(h * sin + w * cos), int(h * cos + w * sin)
    matrix[0, 2] += new_w / 2 - w / 2
    matrix[1, 2] += new_h / 2 - h / 2
    return cv2.warpAffine(template, matrix, (new_w, new_h), flags=cv2.INTER_LINEAR, borderValue=0)


def _ncc(mask: np.ndarray, a: tuple, b: tuple) -> float:
    return max(_ncc_one_way(mask, a, b), _ncc_one_way(mask, b, a))


def _orb_matches(gray: np.ndarray, a: tuple, b: tuple) -> int:
    orb = cv2.ORB_create(nfeatures=500)
    crops = [gray[y:y + h, x:x + w] for x, y, w, h in (a, b)]
    found = [orb.detectAndCompute(c, None) for c in crops]
    if found[0][1] is None or found[1][1] is None:
        return 0
    matches = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(found[0][1], found[1][1])
    return sum(1 for m in matches if m.distance < 40)


def _best_pair(mask: np.ndarray, boxes: list[tuple]) -> tuple[float, tuple | None]:
    best, pair = 0.0, None
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            if not _similar_size(a, b) or abs(a[0] - b[0]) + abs(a[1] - b[1]) < MIN_STAMP_DISTANCE:
                continue
            score = _ncc(mask, a, b)
            if score > best:
                best, pair = score, (a, b)
    return best, pair


def detect_copy_move(img: Image.Image) -> CopyMove:
    best, pair, total = 0.0, None, 0
    for mask in _ink_masks(to_bgr(img)):
        boxes = stamp_candidates(mask)
        total += len(boxes)
        score, candidate = _best_pair(mask, boxes)
        if candidate is not None and score > best:
            best, pair = score, candidate
    if pair is None or best < COPY_MOVE_NCC:
        return CopyMove(found=False, score=round(best, 3), stamp_candidates=total)
    regions = [[x, y, x + w, y + h] for x, y, w, h in pair]
    return CopyMove(found=True, score=round(best, 3), regions=regions,
                    orb_matches=_orb_matches(to_gray(img), *pair), stamp_candidates=total)


def ela(img: Image.Image) -> tuple[Image.Image, float, float]:
    """Return (heatmap image, mean error, 99th percentile error) for the analysed image."""
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=ELA_QUALITY)
    recompressed = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    diff = np.asarray(ImageChops.difference(img.convert("RGB"), recompressed).convert("L"), dtype=np.float32)
    mean, p99 = float(diff.mean()), float(np.percentile(diff, 99))
    amplified = np.clip(diff * ELA_GAIN, 0, 255).astype(np.uint8)
    heat = cv2.applyColorMap(amplified, cv2.COLORMAP_INFERNO)
    heatmap = Image.fromarray(cv2.cvtColor(heat, cv2.COLOR_BGR2RGB))
    return heatmap, round(mean, 2), round(p99, 2)


def heatmap_jpeg(heatmap: Image.Image, max_side: int = 900) -> bytes:
    small = ImageOps.contain(heatmap, (max_side, max_side))
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=70)
    return buf.getvalue()


def _looks_like_screenshot(img: Image.Image) -> bool:
    """Phone screenshot: tall portrait canvas with a near-black band at top and bottom."""
    gray = to_gray(img)
    h, w = gray.shape
    if h < 1.6 * w:
        return False
    band = max(4, h // 40)
    return bool(gray[:band].mean() < 50 and gray[-band:].mean() < 50)


def analyse(img: Image.Image, exif: dict) -> tuple[ForensicReport, bytes]:
    heatmap, ela_mean, ela_p99 = ela(img)
    report = ForensicReport(
        copy_move=detect_copy_move(img), ela_mean=ela_mean, ela_p99=ela_p99, exif=exif,
        looks_like_screenshot=_looks_like_screenshot(img),
    )
    return report, heatmap_jpeg(heatmap)
