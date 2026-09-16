import os

# See api/main.py for why these are required.
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
try:
    import torch  # noqa: F401  — import-order fix, see api/main.py
except ImportError:
    pass

_TESSERACT_WIN_DIR = r"C:\Program Files\Tesseract-OCR"
if os.name == "nt" and os.path.isdir(_TESSERACT_WIN_DIR) and _TESSERACT_WIN_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _TESSERACT_WIN_DIR + os.pathsep + os.environ.get("PATH", "")
