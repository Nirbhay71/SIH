"""EXPERIMENT — NOT USED BY THE PRODUCT. Kept so the result is reproducible and
nobody re-builds it expecting it to work.

Measured outcome (evaluation/tampering_realdoc.py, forgeries built from real
documents): after restricting comparisons to flat blocks it flags 9 of 10
forgeries, but it also flags 100% of the genuine real documents and 100% of
40 genuine synthetic ones (copy-move 100% FP on repeated scan texture;
recompression 57% FP). A detector that flags everything carries no
information, so it is deliberately not wired into scoring. Making it usable
needs real forged/genuine pairs to tune per-method thresholds against.

Localised image-forensics: finds *where* a document was edited, not just
whether it "looks odd".

Why this exists: the older per-field text-manipulation heuristic
(font_spacing_forensics.py) was measured against forgeries built from real
documents (evaluation/tampering_realdoc.py) and scored the untouched originals
and every forgery identically (~0.85-0.9). It responds to the document, not
to an edit. The methods here are the standard localised ones from the image
forensics literature, each of which is defined relative to the *same image's
own statistics*, so an unusual-but-genuine document does not trip them:

  1. Noise-residual inconsistency — every capture pipeline leaves a
     characteristic sensor/compression noise level; pasted, blurred or
     retyped regions carry a different one. Blocks whose residual variance is
     a robust outlier against the rest of the page are suspect.
  2. Local recompression (block-wise ELA) — re-save at a fixed quality and
     compare error per block; a region with a different JPEG history than its
     surroundings responds differently.
  3. Copy-move — a region duplicated elsewhere on the page produces keypoint
     matches related by one consistent translation. Repeated glyphs and MRZ
     filler ("<<<<") also match, so a match only counts if a single
     translation explains many keypoints spread over a real area.

Each returns a score in [0, 1] and a boolean block map; `analyze()` combines
them and returns a heatmap-ready grid. All scores are anchored to the
document's own robust statistics (median/MAD), never to absolute thresholds
tuned on one dataset.
"""
from dataclasses import dataclass

import cv2
import numpy as np

BLOCK = 32
# A block is an outlier when it is this many robust standard deviations from
# the page median. 3.5 is the conventional cut for MAD-based outliers.
_Z_CUT = 3.5


@dataclass
class ForensicsResult:
    noise_score: float
    recompression_score: float
    copy_move_score: float
    score: float
    block_map: np.ndarray  # bool grid, True = suspicious block
    block_size: int = BLOCK


def _robust_z(values: np.ndarray) -> np.ndarray:
    med = np.median(values)
    mad = np.median(np.abs(values - med)) * 1.4826
    return (values - med) / max(mad, 1e-6)


def _block_grid(img_gray: np.ndarray, fn) -> np.ndarray:
    h, w = img_gray.shape
    gh, gw = h // BLOCK, w // BLOCK
    out = np.zeros((gh, gw), dtype=np.float32)
    for r in range(gh):
        for c in range(gw):
            out[r, c] = fn(img_gray[r * BLOCK:(r + 1) * BLOCK, c * BLOCK:(c + 1) * BLOCK])
    return out


def _outlier_score(
    grid: np.ndarray, valid: np.ndarray | None = None, min_area_blocks: int = 3
) -> tuple[float, np.ndarray]:
    """Score how much of the page is a *coherent* robust outlier. Isolated
    single blocks are ignored (text edges do that constantly); an edit is a
    connected region.

    `valid` restricts both the reference statistics and the flagging to
    blocks that are comparable to each other. Without it, a text block's
    residual (dominated by glyph edges) is compared against a blank-paper
    block's (sensor noise), and every printed document looks "inconsistent"
    — measured: this flagged 100% of genuine synthetic documents."""
    if valid is None:
        valid = np.ones(grid.shape, dtype=bool)
    if valid.sum() < 12:
        return 0.0, np.zeros(grid.shape, dtype=bool)
    ref = grid[valid]
    med = np.median(ref)
    mad = max(np.median(np.abs(ref - med)) * 1.4826, 1e-6)
    z = (grid - med) / mad
    z[~valid] = 0.0
    mask = (np.abs(z) > _Z_CUT).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    kept = np.zeros_like(mask, dtype=bool)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= min_area_blocks:
            kept |= labels == i
    if not kept.any():
        return 0.0, kept
    area_fraction = float(kept.mean())
    strength = float(np.clip(np.abs(z[kept]).mean() / 10.0, 0.0, 1.0))
    # An edit covering ~3% of a page with clear strength should already be a
    # strong signal; scale so that maps near 1.
    return float(np.clip(area_fraction / 0.03, 0.0, 1.0) * (0.5 + 0.5 * strength)), kept


def _flat_mask(gray: np.ndarray) -> np.ndarray:
    """Blocks with no strong structure (no text/edges/photo) — the only ones
    whose residual reflects the capture noise rather than the content."""
    grad = cv2.magnitude(cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1))
    energy = _block_grid(grad, lambda b: float(b.mean()))
    return energy < max(np.percentile(energy, 40), 1e-3)


def noise_inconsistency(gray: np.ndarray) -> tuple[float, np.ndarray]:
    denoised = cv2.medianBlur(gray, 3)
    residual = gray.astype(np.float32) - denoised.astype(np.float32)
    grid = _block_grid(residual, lambda b: float(np.log1p(b.var())))
    return _outlier_score(grid, valid=_flat_mask(gray))


def recompression_inconsistency(bgr: np.ndarray) -> tuple[float, np.ndarray]:
    ok, enc = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        return 0.0, np.zeros((1, 1), dtype=bool)
    resaved = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    diff = cv2.absdiff(bgr, resaved).mean(axis=2).astype(np.float32)
    grid = _block_grid(diff, lambda b: float(b.mean()))
    return _outlier_score(grid, valid=_flat_mask(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)))


def copy_move(gray: np.ndarray) -> tuple[float, np.ndarray]:
    h, w = gray.shape
    orb = cv2.ORB_create(nfeatures=3000, fastThreshold=10)
    kps, desc = orb.detectAndCompute(gray, None)
    empty = np.zeros((max(h // BLOCK, 1), max(w // BLOCK, 1)), dtype=bool)
    if desc is None or len(kps) < 40:
        return 0.0, empty

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    pairs = matcher.knnMatch(desc, desc, k=3)
    min_shift = 0.08 * max(h, w)  # ignore matches to neighbouring pixels of the same glyph

    shifts, src_pts, dst_pts = [], [], []
    for group in pairs:
        # group[0] is the keypoint itself; the next-best is its true partner.
        if len(group) < 3:
            continue
        best, second = group[1], group[2]
        if best.distance > 40 or best.distance > 0.7 * second.distance:
            continue
        p, q = np.array(kps[best.queryIdx].pt), np.array(kps[best.trainIdx].pt)
        if np.linalg.norm(p - q) < min_shift:
            continue
        shifts.append(q - p)
        src_pts.append(p)
        dst_pts.append(q)
    if len(shifts) < 12:
        return 0.0, empty

    shifts = np.array(shifts)
    src_pts, dst_pts = np.array(src_pts), np.array(dst_pts)
    # Cluster by translation vector (sign-normalised: a->b and b->a are one edit).
    signs = np.where(shifts[:, 0:1] < 0, -1, 1)
    norm_shifts = shifts * signs
    quant = np.round(norm_shifts / 6.0).astype(int)
    keys, inverse, counts = np.unique(quant, axis=0, return_inverse=True, return_counts=True)
    top = int(np.argmax(counts))
    members = inverse == top
    if counts[top] < 12:
        return 0.0, empty

    pts = np.vstack([src_pts[members], dst_pts[members]])
    # A real duplicated region spans area; a row of repeated letters does not.
    span = pts.max(axis=0) - pts.min(axis=0)
    spread = float(np.prod(span) / (h * w))
    if spread < 0.01 or min(span) < 0.05 * min(h, w):
        return 0.0, empty

    mask = np.zeros((max(h // BLOCK, 1), max(w // BLOCK, 1)), dtype=bool)
    for x, y in pts:
        mask[min(int(y) // BLOCK, mask.shape[0] - 1), min(int(x) // BLOCK, mask.shape[1] - 1)] = True
    score = float(np.clip(counts[top] / 40.0, 0.0, 1.0) * np.clip(spread / 0.05, 0.3, 1.0))
    return score, mask


def analyze(image_bgr: np.ndarray) -> ForensicsResult:
    # Work at a bounded size: block statistics need consistent scale, and the
    # ORB matcher is quadratic in keypoints.
    h, w = image_bgr.shape[:2]
    scale = 1400.0 / max(h, w)
    if scale < 1.0:
        image_bgr = cv2.resize(image_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

    n_score, n_map = noise_inconsistency(gray)
    r_score, r_map = recompression_inconsistency(image_bgr)
    c_score, c_map = copy_move(gray)

    shape = n_map.shape
    block_map = n_map.copy()
    if r_map.shape == shape:
        block_map |= r_map
    if c_map.shape == shape:
        block_map |= c_map

    # Independent methods that flag the *same* region corroborate each other;
    # take the strongest single signal, plus a bonus when two agree, rather
    # than an average that one quiet method would dilute.
    scores = sorted([n_score, r_score, c_score], reverse=True)
    combined = min(1.0, scores[0] + 0.25 * scores[1])
    return ForensicsResult(n_score, r_score, c_score, float(combined), block_map)
