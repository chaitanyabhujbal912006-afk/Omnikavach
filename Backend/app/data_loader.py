from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

import pandas as pd

from app.exceptions import ClinicalDataIncompleteError
from app import schemas


def _get_db_path() -> Path:
    """Get the SQLite database path."""
    db_path = Path(__file__).resolve().parent.parent / "data" / "mimic.db"
    if not db_path.exists():
        raise ClinicalDataIncompleteError(f"Database not found at {db_path}. Run migrate_to_sqlite.py first.")
    return db_path


DB_PATH = _get_db_path()


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _validate_timestamp(timestamp_raw, context: str = "data") -> datetime:
    """Validate and convert timestamp with proper error handling."""
    if pd.isna(timestamp_raw) or not timestamp_raw:
        raise ValueError(f"Invalid timestamp in {context}: {timestamp_raw}")
    try:
        timestamp = pd.to_datetime(timestamp_raw, errors="coerce")
        if pd.isna(timestamp):
            raise ValueError(f"Could not parse timestamp in {context}: {timestamp_raw}")
        if timestamp.year < 1900 or timestamp.year > 2100:
            raise ValueError(f"Timestamp out of reasonable range in {context}: {timestamp}")
        return timestamp.to_pydatetime()
    except Exception as exc:
        raise ValueError(f"Timestamp validation failed in {context}: {exc}") from exc


def _sanitize_string(value, max_length: int = 1000, context: str = "data") -> str:
    """Sanitize string values to prevent injection and ensure reasonable length."""
    if pd.isna(value) or not value:
        return "unknown"
    str_value = str(value).strip()
    if len(str_value) > max_length:
        str_value = str_value[:max_length] + "..."
    dangerous_patterns = ['<script', 'javascript:', 'onload=', 'onerror=', '\x00']
    for pattern in dangerous_patterns:
        if pattern in str_value.lower():
            str_value = "[SANITIZED]"
    return str_value


# Global cache for labels so we don't query the DB 1000 times
_lab_label_map = None
_chart_label_map = None

def _get_lab_label_map(conn) -> Dict[int, str]:
    global _lab_label_map
    if _lab_label_map is None:
        try:
            cursor = conn.execute("SELECT itemid, label FROM D_LABITEMS WHERE label IS NOT NULL")
            _lab_label_map = {row["itemid"]: str(row["label"]) for row in cursor.fetchall()}
        except sqlite3.OperationalError:
            _lab_label_map = {}
    return _lab_label_map

def _get_chart_label_map(conn) -> Dict[int, str]:
    global _chart_label_map
    if _chart_label_map is None:
        try:
            cursor = conn.execute("SELECT itemid, label FROM D_ITEMS WHERE label IS NOT NULL")
            _chart_label_map = {row["itemid"]: str(row["label"]) for row in cursor.fetchall()}
        except sqlite3.OperationalError:
            _chart_label_map = {}
    return _chart_label_map


def get_available_subject_ids(limit: Optional[int] = None) -> List[int]:
    """Return available subject IDs from the SQLite dataset."""
    conn = _get_conn()
    try:
        query = "SELECT DISTINCT subject_id FROM PATIENTS WHERE subject_id IS NOT NULL ORDER BY subject_id"
        if limit:
            query += f" LIMIT {limit}"
        cursor = conn.execute(query)
        return [int(row["subject_id"]) for row in cursor.fetchall()]
    except Exception as exc:
        raise ClinicalDataIncompleteError("Failed to query PATIENTS table") from exc
    finally:
        conn.close()


def get_mimic_patient(subject_id: int) -> schemas.PatientData:
    """Load a patient's labs, vitals, and notes instantly from SQLite."""
    conn = _get_conn()
    
    lab_label_map = _get_lab_label_map(conn)
    chart_label_map = _get_chart_label_map(conn)

    # 1. LAB EVENTS (limit 50 directly in SQL)
    lab_results: List[schemas.LabResult] = []
    try:
        cursor = conn.execute(
            """
            SELECT itemid, valuenum, valueuom, charttime 
            FROM LABEVENTS 
            WHERE subject_id = ? AND valuenum IS NOT NULL
            ORDER BY charttime DESC LIMIT 50
            """, (subject_id,)
        )
        for row in cursor.fetchall():
            try:
                item_id_int = int(row["itemid"])
                item_label = _sanitize_string(lab_label_map.get(item_id_int, f"ITEMID_{item_id_int}"), 100, "lab item_id")
                timestamp = _validate_timestamp(row["charttime"], f"lab result {item_id_int}")
                lab_value = float(row["valuenum"])
                if -1000 <= lab_value <= 10000:
                    lab_results.append(
                        schemas.LabResult(
                            item_id=item_label,
                            value=lab_value,
                            unit=_sanitize_string(row["valueuom"], 20, "lab unit"),
                            timestamp=timestamp,
                        )
                    )
            except Exception:
                continue
    except Exception:
        pass

    # 2. CHART EVENTS / VITALS (limit 80 directly in SQL, we filter more aggressively in Python)
    vital_signs: List[schemas.VitalSign] = []
    try:
        cursor = conn.execute(
            """
            SELECT itemid, valuenum, charttime, storetime 
            FROM CHARTEVENTS 
            WHERE subject_id = ? AND valuenum IS NOT NULL
            ORDER BY charttime DESC LIMIT 300
            """, (subject_id,)
        )
        for row in cursor.fetchall():
            try:
                item_id_int = int(row["itemid"])
                item_label = chart_label_map.get(item_id_int, f"ITEMID_{item_id_int}")
                label_lower = item_label.lower()

                if "heart rate" in label_lower:
                    vital_type = "Heart Rate"
                elif "mean" in label_lower and "pressure" in label_lower:
                    vital_type = "MAP"
                elif "arterial bp" in label_lower and "mean" in label_lower:
                    vital_type = "MAP"
                elif "blood pressure" in label_lower:
                    vital_type = "Blood Pressure"
                else:
                    continue

                # Once we have 50 vitals, stop
                if len(vital_signs) >= 50:
                    break

                timestamp_raw = row["charttime"] or row["storetime"]
                timestamp = pd.to_datetime(timestamp_raw, errors="coerce")
                if pd.isna(timestamp):
                    continue

                vital_signs.append(
                    schemas.VitalSign(
                        type=vital_type,
                        value=float(row["valuenum"]),
                        timestamp=timestamp.to_pydatetime(),
                    )
                )
            except Exception:
                continue
    except Exception:
        pass

    # 3. CLINICAL NOTES (limit 15 directly in SQL)
    clinical_notes: List[schemas.ClinicalNote] = []
    try:
        cursor = conn.execute(
            """
            SELECT row_id, text, category 
            FROM NOTEEVENTS 
            WHERE subject_id = ? AND text IS NOT NULL
            ORDER BY row_id ASC LIMIT 15
            """, (subject_id,)
        )
        for row in cursor.fetchall():
            clinical_notes.append(
                schemas.ClinicalNote(
                    note_id=str(row["row_id"] or "unknown"),
                    text_content=str(row["text"]),
                    category=str(row["category"] or "General"),
                )
            )
    except Exception:
        pass
        
    conn.close()

    # Re-sort lists just in case
    lab_results = sorted(lab_results, key=lambda x: x.timestamp, reverse=True)
    vital_signs = sorted(vital_signs, key=lambda x: x.timestamp, reverse=True)

    return schemas.PatientData(
        lab_results=lab_results,
        vital_signs=vital_signs,
        clinical_notes=clinical_notes,
    )
