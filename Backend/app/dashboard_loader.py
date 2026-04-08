"""
Dashboard data enrichment layer for OmniKavach.

Bridges the gap between raw MIMIC-III clinical data and the frontend's
expected display format. Computes risk scores, assembles timelines,
and generates patient metadata.
"""

from __future__ import annotations

import hashlib
import logging
import math
import time as _time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from app import schemas
from app.data_loader import (
    _get_conn,
    get_available_subject_ids,
    get_mimic_patient,
)
from app.exceptions import ClinicalDataIncompleteError

logger = logging.getLogger(__name__)

# ============================================================
# In-memory Cache (avoids re-processing 78MB CHARTEVENTS per request)
# ============================================================
_cache: Dict[str, Tuple[float, object]] = {}
_CACHE_TTL = 86400  # 24 hours (prevents long loading times during demo)
CUSTOM_NOTES_FILE = Path(__file__).resolve().parent.parent / "data" / "custom_notes.json"
ANALYSIS_HISTORY_FILE = Path(__file__).resolve().parent.parent / "data" / "analysis_history.json"
DEMO_LAB_OVERRIDES_FILE = Path(__file__).resolve().parent.parent / "data" / "demo_lab_overrides.json"


def _normalize_family_communication(payload: Optional[Dict]) -> Optional[Dict]:
    if not payload:
        return None

    translations = payload.get("translations") or []
    if not translations and payload.get("regional"):
        translations = [
            {
                "code": (payload.get("regionalLanguage") or "hi").lower()[:2],
                "label": payload.get("regionalLanguage") or "Hindi",
                "text": payload.get("regional"),
            }
        ]

    return {
        "updatedWindow": payload.get("updatedWindow") or "Last 12 hours",
        "english": payload.get("english") or "",
        "regionalLanguage": payload.get("regionalLanguage") or (translations[0]["label"] if translations else "Hindi"),
        "regional": payload.get("regional") or (translations[0]["text"] if translations else ""),
        "translations": translations,
    }


def _read_custom_notes() -> Dict[str, List[Dict]]:
    """Read custom user notes from disk."""
    if not CUSTOM_NOTES_FILE.exists():
        return {}
    try:
        import json
        with open(CUSTOM_NOTES_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Failed to read custom notes: %s", e)
        return {}


def _read_analysis_history() -> Dict[str, Dict]:
    """Read AI analysis results from SQLite db."""
    history = {}
    try:
        from app.data_loader import _get_conn
        import json
        conn = _get_conn()
        _ensure_analysis_history_schema(conn)
        cursor = conn.execute(
            """
            SELECT subject_id, risk_score, anomalies, recommendations, timestamp,
                   family_english, family_regional, family_language, family_translations_json, outlier_json, handover_json
            FROM analysis_history
            """
        )
        for row in cursor.fetchall():
            family_payload = None
            if row["family_english"]:
                translations = json.loads(row["family_translations_json"]) if row["family_translations_json"] else []
                family_payload = _normalize_family_communication(
                    {
                        "updatedWindow": "Last 12 hours",
                        "english": row["family_english"],
                        "regionalLanguage": row["family_language"] or "Hindi",
                        "regional": row["family_regional"] or "",
                        "translations": translations,
                    }
                )

            history[str(row["subject_id"])] = {
                "risk_score": row["risk_score"],
                "anomalies": json.loads(row["anomalies"]),
                "recommendations": json.loads(row["recommendations"]),
                "timestamp": row["timestamp"],
                "familyCommunication": family_payload,
                "outlierAlert": json.loads(row["outlier_json"]) if row["outlier_json"] else None,
                "handoverSummary": json.loads(row["handover_json"]) if row["handover_json"] else [],
            }
        conn.close()
    except Exception as e:
        logger.error("Failed to read analysis history from SQLite: %s", e)
    return history


def _write_analysis_history(history: Dict[str, Dict]):
    """Write latest AI analysis results to disk."""
    try:
        import json
        with open(ANALYSIS_HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error("Failed to write analysis history: %s", e)


def save_analysis_result(patient_id: str, result: schemas.AnalysisReport):
    """Save a new AI analysis result for a patient into SQLite and invalidate specific caches."""
    try:
        from app.data_loader import _get_conn
        import json
        conn = _get_conn()
        _ensure_analysis_history_schema(conn)
        conn.execute('''
            INSERT OR REPLACE INTO analysis_history 
            (subject_id, risk_score, anomalies, recommendations, timestamp, family_english, family_regional, family_language, family_translations_json, outlier_json, handover_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            str(patient_id),
            result.risk_score,
            json.dumps(result.detected_anomalies),
            json.dumps(result.recommendations),
            datetime.now().isoformat(),
            result.family_communication.english if result.family_communication else None,
            result.family_communication.regional if result.family_communication else None,
            result.family_communication.regionalLanguage if result.family_communication else None,
            json.dumps([item.model_dump() for item in result.family_communication.translations]) if result.family_communication else None,
            json.dumps(result.outlier_alert.model_dump()) if result.outlier_alert else None,
            json.dumps(result.handover_summary or []),
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Failed to save analysis result to SQLite: %s", e)
    
    # Invalidate patient-specific cache
    cache_key = f"patient_{patient_id}"
    if cache_key in _cache:
        del _cache[cache_key]

    # Note: We don't invalidate the dashboard cache anymore because we merge dynamically.


def _read_custom_notes() -> Dict[str, List[Dict]]:
    """Read custom user notes from SQLite db."""
    notes_db = {}
    try:
        from app.data_loader import _get_conn
        conn = _get_conn()
        cursor = conn.execute(
            """
            SELECT subject_id, note_id, text_content, category, timestamp, author, role
            FROM custom_notes
            ORDER BY timestamp ASC
            """
        )
        for row in cursor.fetchall():
            sid = str(row["subject_id"])
            if sid not in notes_db:
                notes_db[sid] = []
            notes_db[sid].append({
                "id": row["note_id"],
                "text": row["text_content"],
                "category": row["category"],
                "timestamp": row["timestamp"],
                "author": row["author"],
                "role": row["role"],
                "canDelete": True,
            })
        conn.close()
    except Exception as e:
        logger.error("Failed to read custom notes from SQLite: %s", e)
    return notes_db


def save_custom_note(patient_id: str, text: str, category: str):
    """Save a new custom note for a patient to SQLite."""
    import uuid
    from datetime import datetime
    
    note_id = f"USER_{uuid.uuid4().hex[:8]}"
    timestamp = datetime.now().isoformat()
    
    try:
        from app.data_loader import _get_conn
        conn = _get_conn()
        conn.execute('''
            INSERT INTO custom_notes 
            (subject_id, note_id, text_content, category, timestamp, author, role)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (str(patient_id), note_id, text, category, timestamp, "Current User", "Clinician"))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error("Failed to save custom note to SQLite: %s", e)
    
    # Invalidate cache for this patient
    cache_key = f"patient_{patient_id}"
    if cache_key in _cache:
        del _cache[cache_key]


def delete_custom_note(patient_id: str, note_id: str) -> bool:
    """Delete a user-added note so it no longer affects views or analysis."""
    try:
        from app.data_loader import _get_conn
        conn = _get_conn()
        cursor = conn.execute(
            "DELETE FROM custom_notes WHERE subject_id = ? AND note_id = ?",
            (str(patient_id), note_id),
        )
        conn.commit()
        conn.close()
        deleted = cursor.rowcount > 0
    except Exception as e:
        logger.error("Failed to delete custom note %s for patient %s: %s", note_id, patient_id, e)
        deleted = False

    cache_key = f"patient_{patient_id}"
    if cache_key in _cache:
        del _cache[cache_key]
    return deleted


def _read_demo_lab_overrides() -> Dict[str, List[Dict]]:
    """Read optional demo lab overlays for selected showcase patients."""
    if not DEMO_LAB_OVERRIDES_FILE.exists():
        return {}

    try:
        import json

        with open(DEMO_LAB_OVERRIDES_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)

        if isinstance(payload, dict):
            return payload
    except Exception as e:
        logger.error("Failed to read demo lab overrides: %s", e)

    return {}


def _merge_demo_lab_overrides(subject_id: int, patient_data: schemas.PatientData) -> None:
    """
    Inject seeded WBC/creatinine demo trends for a few patients when raw data is sparse.
    This keeps the hackathon demo visually complete without changing unrelated patients.
    """
    overrides = _read_demo_lab_overrides()
    sid = str(subject_id)
    entries = overrides.get(sid, [])
    if not entries:
        return

    existing_wbc = any(
        lab.item_id.lower() in {"wbc", "white blood cells", "white blood cell count"}
        for lab in patient_data.lab_results
    )
    existing_creatinine = any("creatinine" in lab.item_id.lower() for lab in patient_data.lab_results)

    if existing_wbc and existing_creatinine:
        return

    if patient_data.vital_signs:
        anchor_time = max(v.timestamp for v in patient_data.vital_signs)
    elif patient_data.lab_results:
        anchor_time = max(l.timestamp for l in patient_data.lab_results)
    else:
        anchor_time = datetime.now()

    for entry in entries:
        item_id = str(entry.get("item_id", "")).strip()
        unit = str(entry.get("unit", "")).strip() or "units"
        values = entry.get("values", [])
        spacing_hours = float(entry.get("spacing_hours", 6))
        start_hours_ago = float(entry.get("start_hours_ago", spacing_hours * max(len(values) - 1, 0)))

        if not item_id or not isinstance(values, list) or not values:
            continue

        label_lower = item_id.lower()
        if label_lower in {"wbc", "white blood cells", "white blood cell count"} and existing_wbc:
            continue
        if "creatinine" in label_lower and existing_creatinine:
            continue

        for index, value in enumerate(values):
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue

            hours_ago = max(start_hours_ago - (index * spacing_hours), 0)
            timestamp = anchor_time - timedelta(hours=hours_ago)
            patient_data.lab_results.append(
                schemas.LabResult(
                    item_id=item_id,
                    value=numeric_value,
                    unit=unit,
                    timestamp=timestamp,
                )
            )

    patient_data.lab_results = sorted(patient_data.lab_results, key=lambda x: x.timestamp, reverse=True)


def _ensure_analysis_history_schema(conn) -> None:
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(analysis_history)").fetchall()
    }
    migrations = {
        "family_english": "ALTER TABLE analysis_history ADD COLUMN family_english TEXT",
        "family_regional": "ALTER TABLE analysis_history ADD COLUMN family_regional TEXT",
        "family_language": "ALTER TABLE analysis_history ADD COLUMN family_language TEXT",
        "family_translations_json": "ALTER TABLE analysis_history ADD COLUMN family_translations_json TEXT",
        "outlier_json": "ALTER TABLE analysis_history ADD COLUMN outlier_json TEXT",
        "handover_json": "ALTER TABLE analysis_history ADD COLUMN handover_json TEXT",
    }
    for column, statement in migrations.items():
        if column not in columns:
            conn.execute(statement)
    conn.commit()


def _cache_get(key: str):
    entry = _cache.get(key)
    if entry and (_time.time() - entry[0]) < _CACHE_TTL:
        return entry[1]
    return None


def _cache_set(key: str, value):
    _cache[key] = (_time.time(), value)

# ============================================================
# Patient Metadata Generation (MIMIC is anonymized)
# ============================================================

# Deterministic pseudonymous names seeded by subject_id
_FIRST_NAMES = [
    "Arjun", "Priya", "Rahul", "Sunita", "Vikram", "Meena",
    "Kartik", "Anjali", "Deepak", "Kavita", "Rajan", "Neha",
    "Suresh", "Pooja", "Arun", "Divya", "Manish", "Rekha",
    "Gaurav", "Sneha", "Rohit", "Lata", "Sanjay", "Isha",
]

_LAST_NAMES = [
    "Sharma", "Patel", "Verma", "Rao", "Singh", "Joshi",
    "Mehta", "Kapoor", "Nair", "Gupta", "Shah", "Kumar",
    "Das", "Reddy", "Bhat", "Desai", "Pillai", "Mishra",
    "Iyer", "Chopra", "Malhotra", "Mukherjee", "Banerjee", "Thakur",
]

_PHYSICIANS = [
    "Dr. S. Mehta", "Dr. R. Nair", "Dr. P. Gupta", "Dr. K. Shah",
    "Dr. A. Kapoor", "Dr. V. Rao", "Dr. N. Pillai", "Dr. M. Desai",
]

_MEDICAL_KEYWORDS = {
    "sepsis": ["sepsis", "septic", "infection", "bacteremia", "SIRS"],
    "renal": ["AKI", "creatinine", "kidney", "oliguria", "CRRT", "nephrotoxins", "hyperkalemia"],
    "cardiac": ["CHF", "heart failure", "cardiac", "BNP", "diuresis", "arrhythmia", "tachycardia"],
    "respiratory": ["pneumonia", "ARDS", "hypoxia", "ventilated", "intubated", "SpO2", "infiltrates"],
    "general": ["hypotension", "lactate", "fever", "deterioration", "mortality"],
}


def _deterministic_pick(items: list, subject_id: int, salt: str = "") -> str:
    """Pick an item deterministically based on subject_id."""
    h = int(hashlib.md5(f"{subject_id}{salt}".encode()).hexdigest(), 16)
    return items[h % len(items)]


def _generate_name(subject_id: int) -> str:
    first = _deterministic_pick(_FIRST_NAMES, subject_id, "first")
    last = _deterministic_pick(_LAST_NAMES, subject_id, "last")
    return f"{first} {last}"


def _generate_bed(subject_id: int, index: int = 0) -> str:
    bay = "A" if (subject_id + index) % 2 == 0 else "B"
    num = ((subject_id + index) % 6) + 1
    return f"{bay}-{num:02d}"


def _generate_mrn(subject_id: int) -> str:
    return f"MRN-{2024 + (subject_id % 3)}-{subject_id:05d}"


def _generate_physician(subject_id: int) -> str:
    return _deterministic_pick(_PHYSICIANS, subject_id, "doc")


# ============================================================
# Risk Score Computation
# ============================================================

def compute_risk_score(
    patient_id: int,
    vital_signs: List[schemas.VitalSign],
    lab_results: List[schemas.LabResult],
    clinical_notes: List[schemas.ClinicalNote] = None,
) -> int:
    """
    Rule-based risk score (0-100) computed from latest vitals, labs, AND notes.
    Now considers keywords in clinical notes for pre-analysis accuracy.
    """
    score = 10  # base score

    # --- Keyword Search in Notes ---
    if clinical_notes:
        from app.engine import _KEYWORD_RULES
        import re
        all_text = " ".join([n.text_content.lower() for n in clinical_notes])
        for pattern, weight, _, _ in _KEYWORD_RULES:
            if re.search(pattern, all_text, re.IGNORECASE):
                # Map 0.1 weight to ~10-15 scale points
                score += int(abs(weight) * 80) 

    # --- Lactate ---
    lactate_values = [
        lab.value for lab in lab_results
        if "lactate" in lab.item_id.lower()
    ]
    if lactate_values:
        latest_lactate = lactate_values[-1]
        if latest_lactate > 4.0:
            score += 30
        elif latest_lactate > 2.0:
            score += 15

    # --- Heart Rate ---
    hr_values = [
        v.value for v in vital_signs
        if v.type == "Heart Rate"
    ]
    if hr_values:
        latest_hr = hr_values[-1]
        if latest_hr > 120:
            score += 25
        elif latest_hr > 100:
            score += 15

    # --- MAP ---
    map_values = [
        v.value for v in vital_signs
        if v.type == "MAP"
    ]
    if map_values:
        latest_map = map_values[-1]
        if latest_map < 65:
            score += 25
        elif latest_map < 75:
            score += 10

    # --- WBC ---
    wbc_labels = ["white blood cells", "wbc", "white blood cell count"]
    wbc_values = [
        lab.value for lab in lab_results
        if lab.item_id.lower() in wbc_labels
    ]
    if wbc_values:
        latest_wbc = wbc_values[-1]
        if latest_wbc > 12 or latest_wbc < 4:
            score += 15

    # --- Blood Pressure ---
    bp_values = [
        v.value for v in vital_signs
        if v.type == "Blood Pressure"
    ]
    if bp_values:
        latest_bp = bp_values[-1]
        if latest_bp < 90:
            score += 10

    return min(score, 100)


def determine_status(risk_score: int) -> str:
    if risk_score >= 75:
        return "critical"
    elif risk_score >= 50:
        return "warning"
    return "stable"


# ============================================================
# Timeline Assembly
# ============================================================

def _detect_outlier_index(values: List[float], threshold: float = 1.5) -> int:
    """Find index of the most extreme outlier using z-score, or -1 if none."""
    if len(values) < 3:
        return -1

    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    std_dev = math.sqrt(variance) if variance > 0 else 0

    if std_dev == 0:
        return -1

    z_scores = [(abs(x - mean) / std_dev, i) for i, x in enumerate(values)]
    max_z, max_idx = max(z_scores, key=lambda x: x[0])

    return max_idx if max_z > threshold else -1


def build_timeline(
    vital_signs: List[schemas.VitalSign],
    lab_results: List[schemas.LabResult],
    num_points: int = 13,
) -> schemas.TimelineData:
    """
    Build a timeline with evenly-spaced data points over 72 hours.
    Buckets lab/vital data into intervals and takes the mean of each bucket.
    """
    # Find time range
    all_times = []
    for v in vital_signs:
        all_times.append(v.timestamp)
    for l in lab_results:
        all_times.append(l.timestamp)

    if not all_times:
        # Return empty timeline
        labels = [f"{i * 6}h" for i in range(num_points)]
        return schemas.TimelineData(
            labels=labels,
            lactate=[0.0] * num_points,
            heartRate=[0.0] * num_points,
            wbc=[0.0] * num_points,
            creatinine=[0.0] * num_points,
            lactateOutlierIndex=-1,
            normalLactateMax=2.0,
        )

    start_time = min(all_times)
    end_time = max(all_times)
    total_hours = max((end_time - start_time).total_seconds() / 3600, 1)
    interval_hours = total_hours / (num_points - 1) if num_points > 1 else total_hours

    labels = []
    lactate_series = []
    hr_series = []
    wbc_series = []
    creatinine_series = []

    wbc_labels = {"white blood cells", "wbc", "white blood cell count"}

    for i in range(num_points):
        bucket_start = start_time + timedelta(hours=i * interval_hours)
        bucket_end = bucket_start + timedelta(hours=interval_hours)

        hour_label = round(i * interval_hours)
        labels.append(f"{hour_label}h")

        # Collect lactate values in this bucket
        bucket_lactate = [
            lab.value for lab in lab_results
            if "lactate" in lab.item_id.lower()
            and bucket_start <= lab.timestamp < bucket_end
        ]
        lactate_series.append(
            round(sum(bucket_lactate) / len(bucket_lactate), 1) if bucket_lactate else 0.0
        )

        # Collect heart rate values in this bucket
        bucket_hr = [
            v.value for v in vital_signs
            if v.type == "Heart Rate"
            and bucket_start <= v.timestamp < bucket_end
        ]
        hr_series.append(
            round(sum(bucket_hr) / len(bucket_hr), 0) if bucket_hr else 0.0
        )

        bucket_wbc = [
            lab.value for lab in lab_results
            if lab.item_id.lower() in wbc_labels
            and bucket_start <= lab.timestamp < bucket_end
        ]
        wbc_series.append(
            round(sum(bucket_wbc) / len(bucket_wbc), 1) if bucket_wbc else 0.0
        )

        bucket_creatinine = [
            lab.value for lab in lab_results
            if "creatinine" in lab.item_id.lower()
            and bucket_start <= lab.timestamp < bucket_end
        ]
        creatinine_series.append(
            round(sum(bucket_creatinine) / len(bucket_creatinine), 2) if bucket_creatinine else 0.0
        )

    # Fill gaps with nearest non-zero value (forward fill then backward fill)
    lactate_series = _fill_gaps(lactate_series)
    hr_series = _fill_gaps(hr_series)
    wbc_series = _fill_gaps(wbc_series)
    creatinine_series = _fill_gaps(creatinine_series)

    # Detect outliers in lactate
    non_zero_lactate = [v for v in lactate_series if v > 0]
    outlier_idx = _detect_outlier_index(lactate_series) if len(non_zero_lactate) >= 3 else -1

    return schemas.TimelineData(
        labels=labels,
        lactate=lactate_series,
        heartRate=hr_series,
        wbc=wbc_series,
        creatinine=creatinine_series,
        lactateOutlierIndex=outlier_idx,
        normalLactateMax=2.0,
    )


def _fill_gaps(series: List[float]) -> List[float]:
    """Forward-fill then backward-fill zero gaps in a series."""
    filled = series[:]
    # Forward fill
    for i in range(1, len(filled)):
        if filled[i] == 0.0 and filled[i - 1] != 0.0:
            filled[i] = filled[i - 1]
    # Backward fill
    for i in range(len(filled) - 2, -1, -1):
        if filled[i] == 0.0 and filled[i + 1] != 0.0:
            filled[i] = filled[i + 1]
    return filled


# ============================================================
# Condition / Diagnosis
# ============================================================

def _get_diagnosis(subject_id: int) -> str:
    """Get the primary admission diagnosis from ADMISSIONS table."""
    try:
        conn = _get_conn()
        cursor = conn.execute(
            "SELECT diagnosis FROM ADMISSIONS WHERE subject_id = ? AND diagnosis IS NOT NULL LIMIT 1",
            (subject_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if row and str(row["diagnosis"]).strip():
            return str(row["diagnosis"]).strip().title()
    except Exception as e:
        logger.warning("Could not load diagnosis for %s: %s", subject_id, e)
    return "ICU Admission"


def _get_admission_date(subject_id: int) -> str:
    """Get admission date from ADMISSIONS table."""
    try:
        conn = _get_conn()
        cursor = conn.execute(
            "SELECT admittime FROM ADMISSIONS WHERE subject_id = ? AND admittime IS NOT NULL LIMIT 1",
            (subject_id,)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            admit = pd.to_datetime(row["admittime"], errors="coerce")
            if pd.notna(admit):
                return admit.strftime("%d %b %Y")
    except Exception as e:
        logger.warning("Could not load admission date for %s: %s", subject_id, e)
    return "Unknown"


def _get_age(subject_id: int) -> int:
    """Calculate approximate age from PATIENTS table dob and ADMISSIONS admittime."""
    try:
        conn = _get_conn()
        cursor = conn.execute(
            "SELECT dob FROM PATIENTS WHERE subject_id = ? LIMIT 1",
            (subject_id,)
        )
        row = cursor.fetchone()
        if row and row["dob"]:
            dob = pd.to_datetime(row["dob"], errors="coerce")
            if pd.notna(dob):
                cursor2 = conn.execute(
                    "SELECT admittime FROM ADMISSIONS WHERE subject_id = ? AND admittime IS NOT NULL LIMIT 1",
                    (subject_id,)
                )
                arow = cursor2.fetchone()
                if arow:
                    admit = pd.to_datetime(arow["admittime"], errors="coerce")
                    if pd.notna(admit):
                        # Convert to pydatetime to avoid Timedelta overflow for patients > 89
                        age = (admit.to_pydatetime() - dob.to_pydatetime()).days // 365
                        # MIMIC caps age at 89 for privacy (values > 89 are typically ~300)
                        conn.close()
                        return min(max(age, 18), 89)
        conn.close()
    except Exception as e:
        logger.warning("Could not compute age for %s: %s", subject_id, e)
    return 65  # sensible default


def _extract_highlighted_words(
    notes: List[schemas.ClinicalNote],
    lab_results: List[schemas.LabResult],
) -> List[str]:
    """Extract clinically relevant keywords from notes and labs for UI highlighting."""
    words = set()
    
    # Check lab names for notable items
    notable_labs = ["lactate", "creatinine", "wbc", "white blood", "bilirubin", "troponin"]
    for lab in lab_results:
        for notable in notable_labs:
            if notable in lab.item_id.lower():
                words.add(lab.item_id)
                break

    # Extract keywords from notes
    all_keywords = []
    for category_keywords in _MEDICAL_KEYWORDS.values():
        all_keywords.extend(category_keywords)
    
    for note in notes:
        text_lower = note.text_content.lower()
        for keyword in all_keywords:
            if keyword.lower() in text_lower:
                words.add(keyword)

    return list(words)[:15]  # cap at 15


def _build_note_displays(notes: List[schemas.ClinicalNote]) -> List[schemas.NoteDisplay]:
    """Convert ClinicalNote objects to display-ready NoteDisplay objects."""
    displays = []
    for i, note in enumerate(notes):
        # Extract time from note or generate based on position
        time_str = "00:00"
        if note.text_content:
            # Try to extract first timestamp-like pattern
            import re
            time_match = re.search(r'(\d{1,2}:\d{2})', note.text_content[:50])
            if time_match:
                time_str = time_match.group(1)
            else:
                time_str = f"{8 + i * 3:02d}:00"
        
        # Determine role from category
        role_map = {
            "Nursing": "ICU Nurse",
            "Physician": "Attending",
            "General": "Attending",
            "Radiology": "Radiologist",
            "Respiratory": "RT",
            "Discharge summary": "Attending",
        }
        role = role_map.get(note.category, "Attending")
        
        # Generate author name
        author = _deterministic_pick(_PHYSICIANS, hash(note.note_id) & 0xFFFFFFFF, "author")
        
        displays.append(schemas.NoteDisplay(
            id=note.note_id,
            time=time_str,
            author=author,
            role=role,
            text=note.text_content[:2000],  # cap length for display
            canDelete=str(note.note_id).startswith("USER_"),
        ))
    
    return displays


# ============================================================
# Public API
# ============================================================

def get_dashboard_patients(limit: int = 20) -> List[schemas.PatientSummary]:
    """
    Return a list of enriched patient summaries for the ward dashboard.
    Results are cached for 5 minutes to avoid re-processing MIMIC CSVs.
    """
    cache_key = f"dashboard_{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        # DYNAMIC MERGE: Ensure AI scores are reflected even on cache hit
        history = _read_analysis_history()
        for p in cached:
            if p.id in history:
                p.riskScore = int(history[p.id]["risk_score"] * 100)
                p.status = determine_status(p.riskScore)
                p.familyCommunication = (
                    schemas.FamilyCommunication(**history[p.id]["familyCommunication"])
                    if history[p.id].get("familyCommunication")
                    else None
                )
        
        logger.info("Dashboard cache hit (merged with history) — returning %d patients", len(cached))
        return cached

    logger.info("Dashboard cache miss — loading MIMIC data (this may take ~60s)...")
    subject_ids = get_available_subject_ids(limit=limit)
    summaries: List[schemas.PatientSummary] = []

    history = _read_analysis_history()
    
    for idx, sid in enumerate(subject_ids):
        try:
            # Check for AI override first
            sid_str = str(sid)
            ai_score = None
            if sid_str in history:
                ai_score = int(history[sid_str]["risk_score"] * 100)

            patient_data = get_mimic_patient(sid)
            
            # Merge custom notes for risk calculation
            custom_notes_db = _read_custom_notes()
            if sid_str in custom_notes_db:
                for cn in custom_notes_db[sid_str]:
                    # Truncate to stay safely under schema max_length (500k)
                    note_text = cn["text"]
                    if len(note_text) > 490000:
                        note_text = note_text[:490000] + "\n[Content truncated for display]"
                    patient_data.clinical_notes.append(schemas.ClinicalNote(
                        note_id=cn["id"],
                        text_content=note_text,
                        category=cn["category"]
                    ))

            # AI Score takes priority over default rule-based score
            rule_risk = compute_risk_score(sid, patient_data.vital_signs, patient_data.lab_results, patient_data.clinical_notes)
            risk = ai_score if ai_score is not None else rule_risk
            
            status = determine_status(risk)
            condition = _get_diagnosis(sid)
            age = _get_age(sid)

            summaries.append(schemas.PatientSummary(
                id=str(sid),
                bed=_generate_bed(sid, idx),
                name=_generate_name(sid),
                age=age,
                status=status,
                condition=condition,
                riskScore=risk,
                familyCommunication=(
                    schemas.FamilyCommunication(**history[sid_str]["familyCommunication"])
                    if sid_str in history and history[sid_str].get("familyCommunication")
                    else None
                ),
            ))
        except Exception as e:
            logger.warning("Could not load patient %s for dashboard: %s", sid, e)
            continue

    summaries.sort(key=lambda p: p.riskScore, reverse=True)
    _cache_set(cache_key, summaries)
    logger.info("Dashboard loaded and cached: %d patients", len(summaries))
    return summaries


def get_enriched_patient(subject_id: int) -> Optional[schemas.EnrichedPatient]:
    """
    Return a fully enriched patient object for the detail view.
    Results are cached for 5 minutes.
    """
    cache_key = f"patient_{subject_id}"
    cached = _cache_get(cache_key)
    if cached is not None:
        # DYNAMIC MERGE: Ensure latest analysis is in enriched view
        history = _read_analysis_history()
        sid_str = str(subject_id)
        if sid_str in history:
            ai = history[sid_str]
            cached.riskScore = int(ai["risk_score"] * 100)
            cached.status = determine_status(cached.riskScore)
            # Construct AISynthesis manually from history
            risk_factors = [schemas.RiskFactor(label=a, severity="critical" if cached.riskScore >= 75 else "warning") for a in ai.get("anomalies", [])]
            recommendations_text = " ".join(ai.get("recommendations", []))
            
            cached.aiSynthesis = schemas.AISynthesis(
                chiefSummary=recommendations_text,
                riskFactors=risk_factors,
                guidelinesReferenced=[
                    schemas.GuidelineRef(name="MIMIC-III Clinical Database", source="PhysioNet", type="dataset")
                ],
                agentTrace=[],
                handoverSummary=ai.get("handoverSummary", []),
                familyCommunication=(
                    schemas.FamilyCommunication(**ai["familyCommunication"])
                    if ai.get("familyCommunication")
                    else None
                ),
                outlierAlert=(
                    schemas.OutlierAlert(**ai["outlierAlert"])
                    if ai.get("outlierAlert")
                    else None
                ),
            )

        logger.info("Patient %s cache hit (merged with history)", subject_id)
        return cached

    patient_data = get_mimic_patient(subject_id)
    
    # MERGE CUSTOM NOTES
    custom_notes_db = _read_custom_notes()
    sid_str = str(subject_id)
    if sid_str in custom_notes_db:
        for cn in custom_notes_db[sid_str]:
            # Truncate to stay safely under schema max_length (500k)
            note_text = cn["text"]
            if len(note_text) > 490000:
                note_text = note_text[:490000] + "\n[Content truncated for display]"
            patient_data.clinical_notes.append(schemas.ClinicalNote(
                note_id=cn["id"],
                text_content=note_text,
                category=cn["category"]
            ))

    _merge_demo_lab_overrides(subject_id, patient_data)

    # Check for AI override
    history = _read_analysis_history()
    sid_str = str(subject_id)
    ai_overrides = history.get(sid_str)
    
    # Calculate rule-based risk (now including notes-based risk)
    rule_risk = compute_risk_score(subject_id, patient_data.vital_signs, patient_data.lab_results, patient_data.clinical_notes)
    
    if ai_overrides:
        risk = int(ai_overrides["risk_score"] * 100)
    else:
        risk = rule_risk

    status = determine_status(risk)
    timeline = build_timeline(patient_data.vital_signs, patient_data.lab_results)
    notes_display = _build_note_displays(patient_data.clinical_notes)
    highlighted = _extract_highlighted_words(patient_data.clinical_notes, patient_data.lab_results)
    condition = _get_diagnosis(subject_id)
    age = _get_age(subject_id)
    admit_date = _get_admission_date(subject_id)

    # Build a basic AI synthesis placeholder (populated fully by /analyze)
    if ai_overrides:
        ai_synthesis = schemas.AISynthesis(
            chiefSummary=ai_overrides["recommendations"][0] if ai_overrides["recommendations"] else "Analysis complete.",
            riskFactors=[schemas.RiskFactor(label=a, severity="critical") for a in ai_overrides["anomalies"]],
            guidelinesReferenced=[
                schemas.GuidelineRef(name="SSC Sepsis Bundle 2021", source="Surviving Sepsis Campaign", type="protocol"),
                schemas.GuidelineRef(name="MIMIC-III Clinical Database", source="PhysioNet / MIT", type="dataset"),
            ],
            agentTrace=[],
            handoverSummary=ai_overrides.get("handoverSummary", []),
            familyCommunication=(
                schemas.FamilyCommunication(**ai_overrides["familyCommunication"])
                if ai_overrides.get("familyCommunication")
                else None
            ),
            outlierAlert=(
                schemas.OutlierAlert(**ai_overrides["outlierAlert"])
                if ai_overrides.get("outlierAlert")
                else None
            ),
        )
    else:
        ai_synthesis = schemas.AISynthesis(
            chiefSummary=f"Patient {subject_id} admitted with {condition}. "
                         f"Current risk score: {risk}%. "
                         f"Data includes {len(patient_data.lab_results)} lab results, "
                         f"{len(patient_data.vital_signs)} vital signs, "
                         f"and {len(patient_data.clinical_notes)} clinical notes. "
                         f"Run AI Agent Analysis for full diagnostic synthesis.",
            riskFactors=_compute_risk_factors(patient_data, risk),
            guidelinesReferenced=[
                schemas.GuidelineRef(name="SSC Sepsis Bundle 2021", source="Surviving Sepsis Campaign", type="protocol"),
                schemas.GuidelineRef(name="MIMIC-III Clinical Database", source="PhysioNet / MIT", type="dataset"),
            ],
            agentTrace=[],
        )

    result = schemas.EnrichedPatient(
        id=str(subject_id),
        bed=_generate_bed(subject_id),
        name=_generate_name(subject_id),
        age=age,
        mrn=_generate_mrn(subject_id),
        status=status,
        condition=condition,
        admitDate=admit_date,
        physician=_generate_physician(subject_id),
        riskScore=risk,
        notes=notes_display,
        highlightedWords=highlighted,
        timeline=timeline,
        aiSynthesis=ai_synthesis,
    )

    _cache_set(cache_key, result)
    return result


def _compute_risk_factors(
    data: schemas.PatientData,
    risk_score: int,
) -> List[schemas.RiskFactor]:
    """Compute risk factors from patient data for display."""
    factors = []

    # Check lactate
    lactate_values = [l.value for l in data.lab_results if "lactate" in l.item_id.lower()]
    if lactate_values and max(lactate_values) > 4.0:
        factors.append(schemas.RiskFactor(label=f"Elevated Lactate ({max(lactate_values):.1f} mmol/L)", severity="critical"))
    elif lactate_values and max(lactate_values) > 2.0:
        factors.append(schemas.RiskFactor(label=f"Mild Lactate Elevation ({max(lactate_values):.1f} mmol/L)", severity="warning"))

    # Check Notes for critical indicators
    if data.clinical_notes:
        from app.engine import _KEYWORD_RULES
        import re
        all_text = " ".join([n.text_content.lower() for n in data.clinical_notes])
        for pattern, _, label, _ in _KEYWORD_RULES:
            if label == "Signs of Improvement":
                continue # don't show improvement as a risk factor here
            if re.search(pattern, all_text, re.IGNORECASE):
                # Avoid duplicate labels
                if not any(f.label == label for f in factors):
                    factors.append(schemas.RiskFactor(label=label, severity="critical" if "Sepsis" in label or "Risk" in label else "warning"))

    # Check heart rate
    hr_values = [v.value for v in data.vital_signs if v.type == "Heart Rate"]
    if hr_values and max(hr_values) > 120:
        factors.append(schemas.RiskFactor(label=f"Tachycardia (HR {max(hr_values):.0f} bpm)", severity="critical"))
    elif hr_values and max(hr_values) > 100:
        factors.append(schemas.RiskFactor(label=f"Elevated Heart Rate ({max(hr_values):.0f} bpm)", severity="warning"))

    # Check MAP
    map_values = [v.value for v in data.vital_signs if v.type == "MAP"]
    if map_values and min(map_values) < 65:
        factors.append(schemas.RiskFactor(label=f"Hypotension (MAP {min(map_values):.0f} mmHg)", severity="critical"))

    # Check WBC
    wbc_labels = ["white blood cells", "wbc", "white blood cell count"]
    wbc_values = [l.value for l in data.lab_results if l.item_id.lower() in wbc_labels]
    if wbc_values:
        latest = wbc_values[-1]
        if latest > 12:
            factors.append(schemas.RiskFactor(label=f"Leukocytosis (WBC {latest:.1f})", severity="warning"))
        elif latest < 4:
            factors.append(schemas.RiskFactor(label=f"Leukopenia (WBC {latest:.1f})", severity="warning"))

    if risk_score >= 75:
        factors.append(schemas.RiskFactor(label="High Composite Risk Score", severity="critical"))

    return factors
