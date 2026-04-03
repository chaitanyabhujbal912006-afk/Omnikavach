from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterator, List, Optional

import pandas as pd

from app.exceptions import ClinicalDataIncompleteError
from app import schemas


def _get_dataset_dir() -> Path:
    """Get and validate the MIMIC dataset directory path."""
    dataset_dir = Path(
        os.getenv(
            "MIMIC_DATA_DIR",
            str(Path(__file__).resolve().parent.parent / "mimic-iii"),
        )
    )
    
    # Validate directory exists and is accessible
    if not dataset_dir.exists():
        raise ClinicalDataIncompleteError(
            f"MIMIC dataset directory not found: {dataset_dir}. "
            f"Set MIMIC_DATA_DIR environment variable or ensure mimic-iii directory exists."
        )
    
    if not dataset_dir.is_dir():
        raise ClinicalDataIncompleteError(
            f"MIMIC path exists but is not a directory: {dataset_dir}"
        )
    
    # Check read permissions
    if not os.access(dataset_dir, os.R_OK):
        raise ClinicalDataIncompleteError(
            f"No read permissions for MIMIC directory: {dataset_dir}"
        )
    
    return dataset_dir


DATASET_DIR = _get_dataset_dir()


def _validate_timestamp(timestamp_raw, context: str = "data") -> datetime:
    """Validate and convert timestamp with proper error handling."""
    if pd.isna(timestamp_raw):
        raise ValueError(f"Invalid timestamp in {context}: {timestamp_raw}")
    
    try:
        timestamp = pd.to_datetime(timestamp_raw, errors="coerce")
        if pd.isna(timestamp):
            raise ValueError(f"Could not parse timestamp in {context}: {timestamp_raw}")
        
        # Validate reasonable date range (1900-2100)
        if timestamp.year < 1900 or timestamp.year > 2100:
            raise ValueError(f"Timestamp out of reasonable range in {context}: {timestamp}")
            
        return timestamp.to_pydatetime()
    except Exception as exc:
        raise ValueError(f"Timestamp validation failed in {context}: {exc}") from exc


def _sanitize_string(value, max_length: int = 1000, context: str = "data") -> str:
    """Sanitize string values to prevent injection and ensure reasonable length."""
    if pd.isna(value):
        return "unknown"
    
    str_value = str(value).strip()
    
    # Length validation
    if len(str_value) > max_length:
        str_value = str_value[:max_length] + "..."
    
    # Basic sanitization
    dangerous_patterns = ['<script', 'javascript:', 'onload=', 'onerror=', '\x00']
    for pattern in dangerous_patterns:
        if pattern in str_value.lower():
            str_value = "[SANITIZED]"
    
    return str_value or "unknown"


def _resolve_dataset_file(stem: str) -> Path:
    """Resolve either compressed or uncompressed CSV file for a MIMIC table."""
    gz = DATASET_DIR / f"{stem}.csv.gz"
    plain = DATASET_DIR / f"{stem}.csv"
    if gz.exists():
        return gz
    if plain.exists():
        return plain
    raise ClinicalDataIncompleteError(
        f"Required MIMIC file is missing: {stem}.csv.gz (or {stem}.csv)"
    )


def _subject_chunks(
    file_path: Path,
    subject_id: int,
    usecols: List[str],
    chunksize: int = 50000,
) -> Iterator[pd.DataFrame]:
    """Yield chunks that contain only rows for a single subject_id."""
    try:
        for chunk in pd.read_csv(file_path, usecols=usecols, chunksize=chunksize):
            if "subject_id" not in chunk.columns:
                continue
            filtered = chunk[chunk["subject_id"] == subject_id]
            if not filtered.empty:
                yield filtered
    except FileNotFoundError as exc:
        raise ClinicalDataIncompleteError(
            f"Required MIMIC file not found: {file_path.name}"
        ) from exc


def _read_label_map(file_path: Path, id_col: str = "itemid") -> Dict[int, str]:
    """Read ITEMID to LABEL map for lookup tables like D_ITEMS and D_LABITEMS."""
    try:
        df = pd.read_csv(file_path, usecols=[id_col, "label"])
    except ValueError:
        return {}
    except FileNotFoundError as exc:
        raise ClinicalDataIncompleteError(
            f"Required dictionary file not found: {file_path.name}"
        ) from exc

    cleaned = df.dropna(subset=[id_col, "label"])
    return {int(row[id_col]): str(row["label"]) for _, row in cleaned.iterrows()}


def get_available_subject_ids(limit: Optional[int] = None) -> List[int]:
    """Return available subject IDs from the MIMIC dataset."""
    patients_file = _resolve_dataset_file("PATIENTS")
    try:
        df = pd.read_csv(patients_file, usecols=["subject_id"])
    except FileNotFoundError as exc:
        raise ClinicalDataIncompleteError("PATIENTS file is unavailable") from exc

    subject_ids = sorted(df["subject_id"].dropna().astype(int).unique().tolist())
    if limit is not None:
        return subject_ids[:limit]
    return subject_ids


def get_mimic_patient(subject_id: int) -> schemas.PatientData:
    """Load a patient's labs, vitals, and notes from MIMIC demo CSVs."""
    labevents_file = _resolve_dataset_file("LABEVENTS")
    chartevents_file = _resolve_dataset_file("CHARTEVENTS")
    noteevents_file = _resolve_dataset_file("NOTEEVENTS")

    d_labitems_file = _resolve_dataset_file("D_LABITEMS")
    d_items_file = _resolve_dataset_file("D_ITEMS")

    lab_label_map = _read_label_map(d_labitems_file)
    chart_label_map = _read_label_map(d_items_file)

    lab_results: List[schemas.LabResult] = []
    for rows in _subject_chunks(
        labevents_file,
        subject_id,
        usecols=["subject_id", "itemid", "valuenum", "valueuom", "charttime"],
    ):
        rows["valuenum"] = pd.to_numeric(rows["valuenum"], errors="coerce")
        rows = rows.dropna(subset=["valuenum"])
        for _, row in rows.iterrows():
            try:
                item_id_int = int(row["itemid"])
                item_label = _sanitize_string(lab_label_map.get(item_id_int, f"ITEMID_{item_id_int}"), 100, "lab item_id")
                
                timestamp_raw = row.get("charttime")
                timestamp = _validate_timestamp(timestamp_raw, f"lab result for item_id {item_id_int}")
                
                # Validate lab value is within reasonable bounds
                lab_value = float(row["valuenum"])
                if lab_value < -1000 or lab_value > 10000:
                    continue  # Skip unreasonable values
                
                lab_results.append(
                    schemas.LabResult(
                        item_id=item_label,
                        value=lab_value,
                        unit=_sanitize_string(row.get("valueuom") or "unknown", 20, "lab unit"),
                        timestamp=timestamp,
                    )
                )
            except (ValueError, TypeError) as exc:
                # Skip malformed rows but continue processing
                continue

    vital_signs: List[schemas.VitalSign] = []
    for rows in _subject_chunks(
        chartevents_file,
        subject_id,
        usecols=["subject_id", "itemid", "valuenum", "valueuom", "charttime", "storetime"],
    ):
        rows["valuenum"] = pd.to_numeric(rows["valuenum"], errors="coerce")
        rows = rows.dropna(subset=["valuenum"])
        for _, row in rows.iterrows():
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

            timestamp_raw = row.get("charttime") or row.get("storetime")
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

    clinical_notes: List[schemas.ClinicalNote] = []
    for rows in _subject_chunks(
        noteevents_file,
        subject_id,
        usecols=["subject_id", "row_id", "text", "category"],
        chunksize=20000,
    ):
        rows = rows.dropna(subset=["text"])
        for _, row in rows.iterrows():
            clinical_notes.append(
                schemas.ClinicalNote(
                    note_id=str(row.get("row_id", "unknown")),
                    text_content=str(row["text"]),
                    category=str(row.get("category") or "General"),
                )
            )

    return schemas.PatientData(
        lab_results=lab_results,
        vital_signs=vital_signs,
        clinical_notes=clinical_notes,
    )
