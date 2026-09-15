"""Downloads/prepares training data (Section 9.2).

HONEST STATUS (see docs/LIMITATIONS.md and the progress notes in
README.md for the full account — do not read this module's success as
implying otherwise):

- MIDV-2020 (genuine class): freely downloadable without an account from
  the official mirrors (ftp://smartengines.com/midv-2020 and
  http://l3i-share.univ-lr.fr). This script downloads it directly.
- SIDTD (labeled forgeries: crop-and-replace, inpaint-and-rewrite): hosted
  behind a TC-11 account signup (http://tc11.cvc.uab.es/datasets/SIDTD_1).
  This requires a human to create an account and accept the dataset's
  license terms — not something this script can or should do
  autonomously. See `download_sidtd_manual_instructions()` below.
- FantasyID (face-swap forgeries): distributed by request via the DeepID
  ICCV Challenge organizers (email-based access grant), not a direct
  download. See `download_fantasyid_manual_instructions()` below.

Because SIDTD and FantasyID cannot be fetched automatically, this script
also provides `generate_synthetic_forgeries()`, which derives a labeled
placeholder "forged" class directly from the downloaded MIDV-2020 genuine
images using the same forgery techniques Module 3 is built to detect
(photo replacement, text-field editing) — clearly labeled as a synthetic
placeholder, not a substitute for SIDTD/FantasyID's real forgery data, so
the fusion model in `train_fusion_model.py` has *something* labeled to
train on in this environment.
"""
import logging
import shutil
import tarfile
from pathlib import Path
from urllib.request import urlretrieve

import cv2
import numpy as np

logger = logging.getLogger("training.prepare_dataset")

DATA_DIR = Path(__file__).resolve().parent / "data"
MIDV2020_DIR = DATA_DIR / "midv2020"
SYNTHETIC_FORGED_DIR = DATA_DIR / "synthetic_forged"

MIDV2020_FTP_URL = "ftp://smartengines.com/midv-2020/dataset/scan_upright.tar"


def download_midv2020(force: bool = False) -> Path:
    """Downloads the MIDV-2020 'scan_upright' subset (~1.1 GB), which is
    freely licensed and requires no account (verified against the
    official readme.txt at download time)."""
    MIDV2020_DIR.mkdir(parents=True, exist_ok=True)
    tar_path = MIDV2020_DIR / "scan_upright.tar"

    if tar_path.exists() and not force:
        logger.info("MIDV-2020 archive already present at %s", tar_path)
        return tar_path

    logger.info("Downloading MIDV-2020 scan_upright.tar (~1.1 GB) — this can take a long time on a slow connection.")
    urlretrieve(MIDV2020_FTP_URL, tar_path)
    return tar_path


def extract_midv2020(tar_path: Path) -> Path:
    extracted_dir = MIDV2020_DIR / "scan_upright"
    if extracted_dir.exists():
        return extracted_dir
    with tarfile.open(tar_path) as tar:
        tar.extractall(MIDV2020_DIR)
    return extracted_dir


def download_sidtd_manual_instructions() -> str:
    return (
        "SIDTD is hosted at http://tc11.cvc.uab.es/datasets/SIDTD_1 behind a free TC-11 account. "
        "To use it: (1) create a TC-11 account and accept the dataset license, (2) download the "
        "released archive, (3) extract it to training/data/sidtd/ preserving its per-forgery-type "
        "subfolder structure (crop_replace/, inpaint_rewrite/). This step requires a human action "
        "and cannot be automated by this script."
    )


def download_fantasyid_manual_instructions() -> str:
    return (
        "FantasyID is distributed on request via the DeepID ICCV Challenge organizers "
        "(https://deepid-iccv.github.io/, data sent by email after a request). Once received, "
        "extract it to training/data/fantasyid/ preserving its bona-fide/ and forged/ subfolders. "
        "This step requires a human action (an access request) and cannot be automated by this script."
    )


def generate_synthetic_forgeries(genuine_dir: Path, output_dir: Path, max_images: int = 200) -> int:
    """Derives a labeled placeholder 'forged' class from genuine MIDV-2020
    images by applying the same forgery techniques Module 3 targets:
    photo-region replacement (pasted rectangle with a mismatched color/
    texture) and a text-field edit (redrawn digits in a plausible field
    location). Clearly a placeholder for real forgery data — see this
    module's top-level docstring and docs/LIMITATIONS.md.

    Returns the number of synthetic forged images written.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    image_paths = list(genuine_dir.rglob("*.jpg"))[:max_images] + list(genuine_dir.rglob("*.png"))[:max_images]

    count = 0
    for path in image_paths[:max_images]:
        image = cv2.imread(str(path))
        if image is None:
            continue

        forged = image.copy()
        h, w = forged.shape[:2]

        # Photo-replacement simulation: paste a mismatched-texture rectangle
        # over a plausible photo region (top-left quadrant, ID-photo shaped).
        x, y = int(w * 0.05), int(h * 0.15)
        pw, ph = int(w * 0.22), int(h * 0.55)
        noise_patch = np.random.randint(0, 255, (ph, pw, 3), dtype=np.uint8)
        forged[y : y + ph, x : x + pw] = cv2.GaussianBlur(noise_patch, (5, 5), 0)

        # Text-field edit simulation: overwrite a horizontal strip with
        # freshly-rendered digits at a different (mismatched) sharpness.
        tx, ty = int(w * 0.45), int(h * 0.55)
        tw, th = int(w * 0.35), int(h * 0.06)
        cv2.rectangle(forged, (tx, ty), (tx + tw, ty + th), (255, 255, 255), -1)
        cv2.putText(forged, "010190", (tx + 5, ty + th - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

        out_path = output_dir / f"forged_{count:04d}.png"
        cv2.imwrite(str(out_path), forged)
        count += 1

    logger.info("Generated %d synthetic placeholder forged images at %s", count, output_dir)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    tar_path = download_midv2020()
    genuine_dir = extract_midv2020(tar_path)
    generate_synthetic_forgeries(genuine_dir, SYNTHETIC_FORGED_DIR)
    print("--- MANUAL STEPS STILL REQUIRED ---")
    print(download_sidtd_manual_instructions())
    print(download_fantasyid_manual_instructions())
