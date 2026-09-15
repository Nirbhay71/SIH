"""Section 5.1 step 2 — document boundary detection via Canny + contours."""
import cv2
import numpy as np

MIN_CONTOUR_AREA_FRACTION = 0.2  # below this fraction of total image area, treat as "no confident boundary"


def detect_document_boundary(image: np.ndarray) -> np.ndarray | None:
    """Returns a 4-point quadrilateral (largest plausible document contour)
    in (x, y) pixel coordinates, or None if no confident boundary was found.

    Assumes `image` is a BGR array (as read by cv2.imread / cv2.imdecode).
    Guarantees: never raises on a well-formed image; returns None rather
    than a low-confidence guess when detection is not confident.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.dilate(edges, np.ones((5, 5), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    image_area = image.shape[0] * image.shape[1]
    best_quad = None
    best_area = 0.0

    for contour in contours:
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        if len(approx) != 4:
            continue
        area = cv2.contourArea(approx)
        if area > best_area:
            best_area = area
            best_quad = approx

    if best_quad is None or (best_area / image_area) < MIN_CONTOUR_AREA_FRACTION:
        return None

    return best_quad.reshape(4, 2)


def crop_to_boundary(image: np.ndarray, quad: np.ndarray) -> np.ndarray:
    """Perspective-warps `image` so `quad` becomes the full output frame."""
    rect = _order_points(quad)
    (tl, tr, br, bl) = rect

    width_a = np.linalg.norm(br - bl)
    width_b = np.linalg.norm(tr - tl)
    max_width = int(max(width_a, width_b))

    height_a = np.linalg.norm(tr - br)
    height_b = np.linalg.norm(tl - bl)
    max_height = int(max(height_a, height_b))

    dst = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype="float32",
    )
    matrix = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(image, matrix, (max_width, max_height))


def _order_points(pts: np.ndarray) -> np.ndarray:
    pts = pts.astype("float32")
    s = pts.sum(axis=1)
    diff = np.diff(pts, axis=1).flatten()
    ordered = np.zeros((4, 2), dtype="float32")
    ordered[0] = pts[np.argmin(s)]        # top-left
    ordered[2] = pts[np.argmax(s)]        # bottom-right
    ordered[1] = pts[np.argmin(diff)]     # top-right
    ordered[3] = pts[np.argmax(diff)]     # bottom-left
    return ordered
