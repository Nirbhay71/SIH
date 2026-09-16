r"""
Demo data seeder for SIH - AI-Based Fake Identity & Document Screening System.

Generates 200 verification records + 8 watchlist entries with realistic
variation across names, nationalities, document types, border checkpoints,
risk levels, and special flags (duplicates, impossible travel, watchlist).

Usage:
    cd backend
    .\venv\Scripts\python.exe seed_demo_data.py
"""
import asyncio
import hashlib
import math
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.config import STORAGE_DIR, BASE_DIR
from app.database import engine, SessionLocal, Base
from app.models import VerificationRecord, WatchlistFace
from app.hashchain import compute_hash
from app.risk import compute_risk_score

# ---------------------------------------------------------------------------
# Pure-python face embedding (numpy DLLs blocked on this machine)
# ---------------------------------------------------------------------------
EMBEDDING_DIM = 64

def embed_face(image_bytes: bytes) -> list[float]:
    digest = hashlib.sha256(image_bytes).digest()
    seed = int.from_bytes(digest[:8], "big")
    rng = random.Random(seed)
    vec = [rng.gauss(0, 1) for _ in range(EMBEDDING_DIM)]
    norm = math.sqrt(sum(v * v for v in vec)) or 1e-9
    return [v / norm for v in vec]

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SEED = 42
random.seed(SEED)

for sub in ("documents", "faces", "heatmaps", "watchlist"):
    (STORAGE_DIR / sub).mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------
def _get_fonts():
    try:
        return ImageFont.truetype("arial.ttf", 28), ImageFont.truetype("arial.ttf", 20)
    except Exception:
        return ImageFont.load_default(), ImageFont.load_default()

FONT_BIG, FONT = _get_fonts()

# ---------------------------------------------------------------------------
# Name / location / document pools
# ---------------------------------------------------------------------------
FIRST_NAMES_MALE = [
    "Ramesh", "Suresh", "Deepak", "Arun", "Rajesh", "Ganesh", "Hari", "Binod",
    "Mohan", "Rajan", "Vikram", "Abdul", "Santosh", "Manoj", "Gopal", "Bhim",
    "Dorje", "Tenzin", "Karma", "Pema", "Dawa", "Mingma", "Nabin", "Devendra",
    "Rakesh", "Kiran", "Pramod", "Sanjay", "Amit", "Rohan", "Nikhil", "Ashok",
    "Bijay", "Dipak", "Hemant", "Jagdish", "Kamal", "Laxman", "Mahesh", "Om",
    "Paras", "Ravi", "Shyam", "Umesh", "Yogesh", "Bishnu", "Chetan", "Dinesh",
]
FIRST_NAMES_FEMALE = [
    "Anjali", "Priya", "Sita", "Nisha", "Lakshmi", "Meena", "Pooja", "Neha",
    "Kavita", "Sunita", "Dolma", "Dipa", "Kamala", "Radha", "Sarita", "Gita",
    "Parvati", "Rekha", "Asha", "Bina", "Chanda", "Durga", "Indira", "Janaki",
    "Kabita", "Maya", "Nirmala", "Rita", "Sabina", "Tara", "Uma", "Yamuna",
]
LAST_NAMES = [
    "Thapa", "Gurung", "Rai", "Sharma", "Magar", "Tamang", "Kumar", "Devi",
    "Wangchuk", "Adhikari", "Verma", "Dorji", "Prasad", "Kumari", "Chaudhary",
    "Mishra", "Lama", "Tshering", "Bahadur", "Joshi", "Basnet", "Chhetri",
    "Pandey", "Singh", "Khan", "Sherpa", "Norbu", "Mehta", "Karki", "Sah",
    "Yadav", "Bhandari", "Tiwari", "Shrestha", "Bose", "Rijal", "Poudel",
    "Ghimire", "Subedi", "Bhatt", "Khatri", "Neupane", "Dahal", "Oli",
]
NATIONALITIES = ["Indian", "Nepali", "Bhutanese"]
DOC_TYPES = ["passport", "visa", "national_id", "driving_license", "permit"]

CHECKPOINTS = {
    "Raxaul":     (26.98, 84.85),
    "Sonauli":    (27.47, 83.52),
    "Jogbani":    (26.40, 87.27),
    "Jaigaon":    (26.83, 89.38),
    "Panitanki":  (26.34, 87.99),
    "Banbasa":    (28.99, 80.07),
    "Rupaidiha":  (28.03, 81.62),
    "Sunauli-W":  (27.48, 83.50),
    "Delhi-IGI":  (28.56, 77.10),
    "Kolkata":    (22.65, 88.45),
}
CHECKPOINT_NAMES = list(CHECKPOINTS.keys())

BORDER_COLORS = {
    "passport": (30, 60, 120),
    "visa": (20, 100, 60),
    "national_id": (100, 30, 30),
    "driving_license": (80, 60, 20),
    "permit": (50, 50, 100),
}

# Watchlist profiles — defined before generate_travelers() so a "watchlist"
# scenario can assign one of these actual names/labels to the traveler,
# instead of a random name matched to an unrelated random label (the
# original version of this script picked watchlist_match_ref independently
# of the traveler's own random name, e.g. a generated "Priya Sharma" could
# get flagged against "SSB-ALERT-AK1987" — Abdul Khan's entry — which tells
# an incoherent story in the demo).
WATCHLIST_PROFILES = [
    {"name": "Vikram Singh", "label": "INTERPOL-RED-VS2024"},
    {"name": "Abdul Khan", "label": "SSB-ALERT-AK1987"},
    {"name": "Ravi Shankar", "label": "NIA-LOOKOUT-RS1976"},
    {"name": "Unknown Suspect-1", "label": "INTEL-WATCH-UNK003"},
    {"name": "Unknown Suspect-2", "label": "RAW-ALERT-SA2025"},
    {"name": "Unknown Suspect-3", "label": "IB-WATCH-SB2026"},
    {"name": "Unknown Suspect-4", "label": "CBI-REF-UNK041"},
    {"name": "Unknown Suspect-5", "label": "SSB-INTEL-UNK055"},
]
WATCHLIST_NAME_TO_LABEL = {wp["name"]: wp["label"] for wp in WATCHLIST_PROFILES}

# ---------------------------------------------------------------------------
# Image generators
# ---------------------------------------------------------------------------
def generate_document_image(name, doc_number, nationality, dob, expiry, doc_type, tampered=False):
    color = BORDER_COLORS.get(doc_type, (30, 60, 120))
    img = Image.new("RGB", (900, 560), (245, 245, 240))
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 889, 549], outline=color, width=4)
    title = doc_type.replace("_", " ").upper()
    draw.text((40, 30), f"REPUBLIC OF DEMOSTAN - {title}", fill=color, font=FONT_BIG)
    photo_fill = (180, 140, 140) if tampered else (210, 210, 210)
    photo_outline = (200, 0, 0) if tampered else (0, 0, 0)
    draw.rectangle([40, 90, 260, 340], fill=photo_fill, outline=photo_outline, width=3 if tampered else 1)
    draw.text((70, 200), "SWAPPED" if tampered else "PHOTO", fill=(120, 0, 0) if tampered else (90, 90, 90), font=FONT)
    fields = [("Name", name), ("Document No.", doc_number), ("Nationality", nationality), ("DOB", dob), ("Expiry", expiry)]
    y = 100
    for label, value in fields:
        draw.text((300, y), f"{label}:", fill=(30, 30, 30), font=FONT)
        draw.text((520, y), str(value), fill=(0, 0, 0), font=FONT)
        y += 40
    if tampered:
        draw.rectangle([510, y - 42, 700, y - 18], outline=(200, 0, 0), width=2)
    return img

def generate_face_image(name_seed, variant=0):
    random.seed(hash(name_seed) + variant)
    bg = (random.randint(180, 240), random.randint(180, 240), random.randint(180, 240))
    img = Image.new("RGB", (300, 400), bg)
    draw = ImageDraw.Draw(img)
    cx, cy = 150, 160
    skin = (255, random.randint(200, 230), random.randint(170, 200))
    draw.ellipse([cx-80, cy-100, cx+80, cy+100], fill=skin, outline=(60, 40, 20), width=2)
    draw.ellipse([cx-35, cy-15, cx-15, cy+5], fill=(60, 60, 60))
    draw.ellipse([cx+15, cy-15, cx+35, cy+5], fill=(60, 60, 60))
    draw.arc([cx-30, cy+20, cx+30, cy+50], 0, 180, fill=(180, 50, 50), width=2)
    draw.text((40, 350), name_seed[:20], fill=(40, 40, 40), font=FONT)
    return img

def generate_heatmap(tampering_score):
    img = Image.new("RGB", (900, 560), (20, 20, 40))
    draw = ImageDraw.Draw(img, "RGBA")
    if tampering_score > 0.5:
        for _ in range(random.randint(2, 5)):
            x, y = random.randint(50, 700), random.randint(50, 400)
            w, h = random.randint(80, 200), random.randint(40, 120)
            draw.rectangle([x, y, x+w, y+h], fill=(255, 50, 30, int(min(tampering_score*200, 200))))
    elif tampering_score > 0.25:
        for _ in range(random.randint(1, 2)):
            x, y = random.randint(50, 700), random.randint(50, 400)
            w, h = random.randint(60, 120), random.randint(30, 80)
            draw.rectangle([x, y, x+w, y+h], fill=(255, 180, 30, int(tampering_score*150)))
    else:
        draw.rectangle([10, 10, 889, 549], fill=(30, 200, 60, 40))
    draw.text((20, 520), f"Tampering Score: {tampering_score:.2f}", fill=(255, 255, 255), font=FONT)
    return img

# ---------------------------------------------------------------------------
# Generate 200 traveler profiles programmatically
# ---------------------------------------------------------------------------
def _random_name():
    if random.random() < 0.5:
        first = random.choice(FIRST_NAMES_MALE)
    else:
        first = random.choice(FIRST_NAMES_FEMALE)
    last = random.choice(LAST_NAMES)
    return f"{first} {last}"

def _random_dob():
    age_days = random.randint(18*365, 65*365)
    return (datetime.now() - timedelta(days=age_days)).date().isoformat()

def _random_checkpoint():
    name = random.choice(CHECKPOINT_NAMES)
    lat, lon = CHECKPOINTS[name]
    # Add small jitter
    return lat + random.uniform(-0.05, 0.05), lon + random.uniform(-0.05, 0.05)

def generate_travelers(count=200):
    travelers = []

    # Distribution: 50% low, 25% medium, 15% high, 5% duplicate, 5% impossible travel
    n_low = int(count * 0.50)        # 100
    n_medium = int(count * 0.25)     # 50
    n_high = int(count * 0.15)       # 30
    n_duplicate = int(count * 0.05)  # 10
    n_impossible = count - n_low - n_medium - n_high - n_duplicate  # 10

    # --- LOW RISK ---
    for _ in range(n_low):
        lat, lon = _random_checkpoint()
        travelers.append({
            "name": _random_name(),
            "nationality": random.choice(NATIONALITIES),
            "doc_type": random.choice(DOC_TYPES),
            "dob": _random_dob(),
            "direction": random.choice(["entry", "exit"]),
            "lat": round(lat, 4), "lon": round(lon, 4),
            "tampered": False,
            "decision": "approved",
        })

    # --- MEDIUM RISK ---
    # Each scenario stacks two moderate factors so the total reliably lands
    # in the 31-65 point band under app/risk.py's actual weights (a single
    # factor alone — e.g. only an expired-document validation failure at 10
    # points, or "pending" with no risk-affecting flag at all — never clears
    # 31, so those don't appear here as standalone scenarios; see
    # generate_travelers()'s HIGH RISK comment for why "borderline" (not
    # confirmed) face mismatch is what belongs in medium, not "low_tampering"-
    # style single flags).
    medium_scenarios = ["expired_plus_tamper", "moderate_tamper", "borderline_face_plus_tamper"]
    for _ in range(n_medium):
        lat, lon = _random_checkpoint()
        scenario = random.choice(medium_scenarios)
        t = {
            "name": _random_name(),
            "nationality": random.choice(NATIONALITIES),
            "doc_type": random.choice(DOC_TYPES),
            "dob": _random_dob(),
            "direction": random.choice(["entry", "exit"]),
            "lat": round(lat, 4), "lon": round(lon, 4),
            "tampered": True,
            "medium_tampering": True,
            "decision": random.choice(["approved", "escalated", None]),
        }
        if scenario == "expired_plus_tamper":
            t["force_expired"] = True
        elif scenario == "borderline_face_plus_tamper":
            t["force_borderline_face_mismatch"] = True
        # "moderate_tamper" needs no extra flag — tampered + medium_tampering
        # (format-consistency failure + a mid-range tampering score) is
        # already enough on its own to land in the medium band.
        travelers.append(t)

    # --- HIGH RISK ---
    # app/risk.py's TAMPERING_WEIGHT caps tampering's own contribution at 40
    # points, so severe tampering alone (even score 1.0) plus an expiry and
    # format-consistency failure (40+10+10=60) still falls short of the
    # 66-point "high" floor — a standalone "heavy tampering only" scenario
    # can never reliably reach high under the current weights. Reaching
    # "high" without a flat-100 watchlist hit needs at least one more
    # independently-scored factor (impossible travel, or — combined with
    # tampering+expiry here — a face mismatch confirmed enough to trigger
    # app/risk.py's FACE_CONFIRMED_MISMATCH_POINTS bonus).
    high_scenarios = ["watchlist", "severe_multi_factor"]
    for _ in range(n_high):
        lat, lon = _random_checkpoint()
        scenario = random.choice(high_scenarios)
        t = {
            "name": _random_name(),
            "nationality": random.choice(NATIONALITIES),
            "doc_type": random.choice(DOC_TYPES),
            "dob": _random_dob(),
            "direction": random.choice(["entry", "exit"]),
            "lat": round(lat, 4), "lon": round(lon, 4),
            "tampered": True,
            "decision": random.choice(["rejected", "escalated", None]),
        }
        if scenario == "watchlist":
            # Use an actual watchlist profile's name so the traveler's OCR'd
            # identity is coherent with which entry they're being flagged
            # against, instead of a random name matched to an unrelated label.
            wp = random.choice(WATCHLIST_PROFILES)
            t["name"] = wp["name"]
            t["watchlist_match"] = True
            t["decision"] = random.choice(["rejected", "escalated"])
        elif scenario == "severe_multi_factor":
            t["force_expired"] = True
            t["force_face_mismatch"] = True
        travelers.append(t)

    # --- DUPLICATES ---
    # Pick random earlier records to duplicate
    base_count = len(travelers)
    for _ in range(n_duplicate):
        dup_idx = random.randint(0, min(base_count - 1, n_low - 1))
        orig = travelers[dup_idx]
        lat, lon = _random_checkpoint()
        t = {
            "name": orig["name"],
            "nationality": orig["nationality"],
            "doc_type": orig["doc_type"],
            "dob": orig["dob"],
            "direction": random.choice(["entry", "exit"]),
            "lat": round(lat, 4), "lon": round(lon, 4),
            "tampered": False,
            "decision": random.choice([None, "escalated"]),
            "is_duplicate": True,
            "duplicate_of_index": dup_idx,
        }
        travelers.append(t)

    # --- IMPOSSIBLE TRAVEL ---
    for _ in range(n_impossible):
        dup_idx = random.randint(0, min(base_count - 1, n_low - 1))
        orig = travelers[dup_idx]
        # Pick a checkpoint far from the original
        far_lat, far_lon = _random_checkpoint()
        while abs(far_lat - orig["lat"]) < 1.0 and abs(far_lon - orig["lon"]) < 1.0:
            far_lat, far_lon = _random_checkpoint()
        t = {
            "name": orig["name"],
            "nationality": orig["nationality"],
            "doc_type": orig["doc_type"],
            "dob": orig["dob"],
            "direction": random.choice(["entry", "exit"]),
            "lat": round(far_lat, 4), "lon": round(far_lon, 4),
            "tampered": random.random() < 0.2,
            "decision": random.choice(["escalated", "rejected"]),
            "is_impossible_travel": True,
            "duplicate_of_index": dup_idx,
        }
        if t["tampered"]:
            t["low_tampering"] = True
        travelers.append(t)

    return travelers

TRAVELERS = generate_travelers(200)


# ---------------------------------------------------------------------------
# Main seeding logic
# ---------------------------------------------------------------------------
async def seed():
    from app.database import init_db
    await init_db()

    async with SessionLocal() as db:
        from sqlalchemy import select, func
        count_result = await db.execute(select(func.count()).select_from(VerificationRecord))
        existing_count = count_result.scalar()
        if existing_count and existing_count > 0:
            print(f"[!] Database already has {existing_count} records. Clearing...")
            await db.execute(VerificationRecord.__table__.delete())
            await db.execute(WatchlistFace.__table__.delete())
            await db.commit()

        print(f"[*] Seeding {len(TRAVELERS)} traveler records + {len(WATCHLIST_PROFILES)} watchlist entries...\n")

        # ----- Watchlist -----
        watchlist_labels = set()
        for wp in WATCHLIST_PROFILES:
            face_img = generate_face_image(wp["name"])
            photo_path = STORAGE_DIR / "watchlist" / f"{wp['label'].replace(' ', '_')}.png"
            face_img.save(photo_path)
            face_bytes = photo_path.read_bytes()
            entry = WatchlistFace(
                reference_label=wp["label"],
                embedding=embed_face(face_bytes),
                photo_path=str(photo_path),
                uploaded_by="admin",
            )
            db.add(entry)
            watchlist_labels.add(wp["label"])
            print(f"  [WATCHLIST] {wp['label']}")

        await db.flush()
        print()

        # ----- Verification Records -----
        records = []
        prev_hash = ""
        chain_seq = 0
        base_time = datetime.utcnow() - timedelta(hours=24)
        # Spread 200 records over 24 hours = ~7.2 min apart
        time_step_minutes = (24 * 60) / len(TRAVELERS)

        counters = {"low": 0, "medium": 0, "high": 0}

        for i, t in enumerate(TRAVELERS):
            session_id = str(uuid.uuid4())
            record_id = str(uuid.uuid4())
            created_at = base_time + timedelta(minutes=i * time_step_minutes + random.uniform(-2, 2))

            is_tampered = t.get("tampered", False)
            force_expired = t.get("force_expired", False)

            issue_date = (datetime.now() - timedelta(days=random.randint(200, 1500))).date()
            if force_expired or (is_tampered and not t.get("low_tampering")):
                expiry_date = (datetime.now() - timedelta(days=random.randint(10, 365))).date()
            else:
                expiry_date = (datetime.now() + timedelta(days=random.randint(365, 3650))).date()

            doc_number = f"{t['nationality'][:1].upper()}{random.randint(1000000, 9999999)}"

            # -- Images --
            doc_img = generate_document_image(t["name"], doc_number, t["nationality"], t["dob"], str(expiry_date), t["doc_type"], is_tampered)
            doc_path = STORAGE_DIR / "documents" / f"{session_id}_doc.png"
            doc_img.save(doc_path)
            doc_bytes = doc_path.read_bytes()

            face_img = generate_face_image(t["name"], variant=0 if not t.get("force_face_mismatch") else 1)
            face_path = STORAGE_DIR / "faces" / f"{session_id}_face.png"
            face_img.save(face_path)
            face_bytes = face_path.read_bytes()
            live_embedding = embed_face(face_bytes)

            # -- OCR --
            low_conf_field = random.choice(["name", "dob", "doc_number"]) if random.random() < 0.12 else None
            def _conf(low=False):
                return round(random.uniform(0.35, 0.55) if low else random.uniform(0.88, 0.99), 2)

            ocr_result = {
                "doc_type": t["doc_type"],
                "fields": {
                    "name": {"value": t["name"], "confidence": _conf(low_conf_field == "name")},
                    "document_number": {"value": doc_number, "confidence": _conf(low_conf_field == "doc_number")},
                    "nationality": {"value": t["nationality"], "confidence": _conf()},
                    "date_of_birth": {"value": t["dob"], "confidence": _conf(low_conf_field == "dob")},
                    "date_of_issue": {"value": str(issue_date), "confidence": _conf()},
                    "date_of_expiry": {"value": str(expiry_date), "confidence": _conf()},
                    "gender": {"value": random.choice(["M", "F"]), "confidence": _conf()},
                },
                "low_confidence_fields": [low_conf_field] if low_conf_field else [],
                "face_crop": "placeholder",
            }

            # -- Validation --
            failures = []
            if force_expired or (is_tampered and expiry_date < datetime.now().date()):
                failures.append({"rule": "expiry_date_valid", "detail": f"Expired on {expiry_date}."})
            if is_tampered:
                failures.append({"rule": "format_consistency", "detail": "Format inconsistency detected."})
            validation_result = {"passed": len(failures) == 0, "failure_count": len(failures), "failures": failures}

            # -- Tampering --
            if t.get("medium_tampering"):
                # Tuned so tampering_score * TAMPERING_WEIGHT(40) + the
                # format-consistency failure (10) alone lands ~32-36 —
                # comfortably in the medium band on its own, see the medium
                # scenario comment in generate_travelers().
                tampering_score = round(random.uniform(0.55, 0.65), 2)
            elif is_tampered and not t.get("low_tampering"):
                tampering_score = round(random.uniform(0.60, 0.95), 2)
            elif is_tampered and t.get("low_tampering"):
                tampering_score = round(random.uniform(0.30, 0.55), 2)
            else:
                tampering_score = round(random.uniform(0.02, 0.15), 2)

            flagged_regions = []
            if tampering_score > 0.25:
                possible = ["photo_area", "dob_field", "expiry_field", "mrz_zone", "stamp_area", "signature"]
                flagged_regions = random.sample(possible, k=min(random.randint(1, 3), len(possible)))

            heatmap_img = generate_heatmap(tampering_score)
            heatmap_path = STORAGE_DIR / "heatmaps" / f"{session_id}.png"
            heatmap_img.save(heatmap_path)

            # -- Face --
            if t.get("force_face_mismatch"):
                face_match_score = round(random.uniform(0.15, 0.45), 3)
            elif t.get("force_borderline_face_mismatch"):
                # Deliberately kept >= 0.5 (app/risk.py's
                # FACE_CONFIRMED_MISMATCH_THRESHOLD) — a borderline/uncertain
                # match gets only the scaled penalty, not the +50 "these are
                # almost certainly different people" bonus that
                # force_face_mismatch's lower range triggers.
                face_match_score = round(random.uniform(0.55, 0.70), 3)
            elif is_tampered and tampering_score > 0.6:
                face_match_score = round(random.uniform(0.50, 0.72), 3)
            else:
                face_match_score = round(random.uniform(0.85, 0.99), 3)

            liveness_passed = random.random() > 0.04

            # -- Watchlist --
            watchlist_match = t.get("watchlist_match", False)
            watchlist_match_ref = WATCHLIST_NAME_TO_LABEL.get(t["name"]) if watchlist_match else None
            if watchlist_match and watchlist_match_ref is None:
                # Shouldn't happen given generate_travelers() now assigns a
                # real watchlist name whenever watchlist_match is set, but
                # fail loud rather than silently seeding an incoherent
                # match/label pair if that assumption ever breaks.
                raise AssertionError(f"watchlist_match=True for '{t['name']}' but no matching WATCHLIST_PROFILES entry")

            # -- Duplicate / impossible travel --
            duplicate_of_record_id = None
            travel_direction_flag = "not_applicable"
            impossible_travel_flag = False
            impossible_travel_detail = None

            if t.get("is_duplicate") and t.get("duplicate_of_index", 0) < len(records):
                dup_idx = t["duplicate_of_index"]
                duplicate_of_record_id = records[dup_idx].id
                if records[dup_idx].travel_direction == t["direction"]:
                    travel_direction_flag = "suspicious"
                else:
                    travel_direction_flag = "consistent"

            if t.get("is_impossible_travel") and t.get("duplicate_of_index", 0) < len(records):
                dup_idx = t["duplicate_of_index"]
                duplicate_of_record_id = records[dup_idx].id
                orig = records[dup_idx]
                R = 6371.0
                p1, p2 = math.radians(orig.latitude or 0), math.radians(t["lat"])
                dphi = math.radians(t["lat"] - (orig.latitude or 0))
                dlambda = math.radians(t["lon"] - (orig.longitude or 0))
                a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlambda/2)**2
                distance_km = 2 * R * math.asin(math.sqrt(a))
                elapsed_hours = max((created_at - orig.created_at).total_seconds() / 3600.0, 1e-6)
                required_speed = distance_km / elapsed_hours
                impossible_travel_flag = required_speed > 900.0
                impossible_travel_detail = {
                    "distance_km": round(distance_km, 2),
                    "time_elapsed_minutes": round(elapsed_hours * 60, 1),
                    "required_speed_kmh": round(required_speed, 1),
                }

            # -- Risk --
            risk = compute_risk_score(
                validation_failure_count=len(failures),
                tampering_score=tampering_score,
                face_similarity_score=face_match_score,
                watchlist_match=watchlist_match,
                travel_direction_flag=travel_direction_flag,
                impossible_travel_flag=impossible_travel_flag,
            )
            counters[risk["risk_level"]] += 1

            # -- Hash chain --
            record_data = {
                "id": record_id, "session_id": session_id, "doc_type": t["doc_type"],
                "doc_number": doc_number, "name": t["name"], "dob": t["dob"],
                "tampering_score": tampering_score, "face_match_score": face_match_score,
                "watchlist_match": watchlist_match, "risk_score": risk["risk_score"],
                "risk_level": risk["risk_level"], "officer_decision": t.get("decision"),
            }
            record_hash = compute_hash(record_data, prev_hash) if t.get("decision") else None

            record = VerificationRecord(
                id=record_id, session_id=session_id, created_at=created_at,
                doc_type=t["doc_type"], doc_number=doc_number,
                name=t["name"], dob=t["dob"], nationality=t["nationality"],
                expiry_date=str(expiry_date),
                document_image_path=str(doc_path),
                ocr_raw_json=ocr_result, validation_result_json=validation_result,
                tampering_score=tampering_score,
                tampering_result_json={"flagged_regions": flagged_regions},
                tampering_heatmap_path=str(heatmap_path),
                face_match_score=face_match_score, liveness_passed=liveness_passed,
                live_face_embedding=live_embedding, live_face_image_path=str(face_path),
                watchlist_match=watchlist_match, watchlist_match_ref=watchlist_match_ref,
                latitude=t["lat"], longitude=t["lon"],
                travel_direction=t["direction"],
                duplicate_of_record_id=duplicate_of_record_id,
                travel_direction_flag=travel_direction_flag,
                impossible_travel_flag=impossible_travel_flag,
                impossible_travel_detail_json=impossible_travel_detail,
                risk_score=risk["risk_score"], risk_level=risk["risk_level"],
                risk_breakdown_json=risk["risk_breakdown"],
                officer_decision=t.get("decision"),
                decided_at=created_at + timedelta(minutes=random.randint(2, 15)) if t.get("decision") else None,
                record_hash=record_hash,
                prev_hash=prev_hash if record_hash else None,
                chain_sequence=chain_seq if record_hash else None,
            )
            db.add(record)
            records.append(record)
            if record_hash:
                prev_hash = record_hash
                chain_seq += 1

            # Progress every 20 records
            if (i + 1) % 20 == 0 or i == len(TRAVELERS) - 1:
                print(f"  [{i+1:3d}/{len(TRAVELERS)}] seeded...")

        await db.commit()

        print(f"\n[OK] Seeded {len(records)} verification records + {len(WATCHLIST_PROFILES)} watchlist entries.")
        print(f"     LOW: {counters['low']}  |  MEDIUM: {counters['medium']}  |  HIGH: {counters['high']}")
        print(f"     Database: {BASE_DIR / 'app.db'}")
        print(f"     Storage:  {STORAGE_DIR}")


if __name__ == "__main__":
    asyncio.run(seed())
