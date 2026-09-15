"""Section 5.1 step 1 — format normalization.

Converts any accepted input format to a lossless in-memory PNG-encoded
array. Critically: never re-saves as JPEG at this stage — a JPEG
re-compression here would corrupt Module 3's Error Level Analysis later
(Section 7.2, Section 12A). The untouched original bytes are always kept
alongside the normalized array so Module 3 can work from a clean
reference.
"""
import io

import cv2
import numpy as np
from PIL import Image

SUPPORTED_RASTER_EXTENSIONS = {"jpg", "jpeg", "png", "tif", "tiff"}


class UnsupportedFormatError(Exception):
    pass


def normalize_to_array(raw_bytes: bytes, filename_hint: str = "") -> np.ndarray:
    """Decodes `raw_bytes` into a BGR numpy array (OpenCV convention).

    Supports JPG/JPEG/PNG/TIFF directly. PDF and HEIC support depend on
    optional libraries (`pymupdf`, `pillow-heif`) being installed; if
    unavailable, raises UnsupportedFormatError with a clear message rather
    than silently mis-decoding — this is a documented, environment-
    dependent limitation (see README.md "Optional format support").
    """
    ext = filename_hint.rsplit(".", 1)[-1].lower() if "." in filename_hint else ""

    if ext == "pdf" or raw_bytes[:4] == b"%PDF":
        return _decode_pdf_first_page(raw_bytes)

    if ext == "heic" or ext == "heif":
        return _decode_heic(raw_bytes)

    try:
        pil_image = Image.open(io.BytesIO(raw_bytes))
        pil_image = pil_image.convert("RGB")
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
    except Exception as exc:  # Pillow raises various subclasses of UnidentifiedImageError
        raise UnsupportedFormatError(f"Could not decode image ({filename_hint or 'no filename hint'}): {exc}") from exc


def _decode_pdf_first_page(raw_bytes: bytes, dpi: int = 300) -> np.ndarray:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise UnsupportedFormatError(
            "PDF input requires the optional 'pymupdf' dependency, which is not installed in this environment."
        ) from exc

    doc = fitz.open(stream=raw_bytes, filetype="pdf")
    page = doc.load_page(0)
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def _decode_heic(raw_bytes: bytes) -> np.ndarray:
    try:
        import pillow_heif
    except ImportError as exc:
        raise UnsupportedFormatError(
            "HEIC input requires the optional 'pillow-heif' dependency, which is not installed in this environment."
        ) from exc

    heif_file = pillow_heif.read_heif(raw_bytes)
    pil_image = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, "raw")
    return cv2.cvtColor(np.array(pil_image.convert("RGB")), cv2.COLOR_RGB2BGR)


def encode_png(image: np.ndarray) -> bytes:
    """Lossless internal representation, per Section 5.1 step 1."""
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("PNG encoding failed.")
    return buf.tobytes()
