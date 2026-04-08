import sqlite3
import pandas as pd
import json
import os
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent
MIMIC_DIR = BASE_DIR / "mimic-iii"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "mimic.db"

# Ensure data dir exists
os.makedirs(DATA_DIR, exist_ok=True)

# Remove existing db if restarting migration
if DB_PATH.exists():
    os.remove(DB_PATH)

print(f"Creating highly-indexed SQLite Database at {DB_PATH}")
conn = sqlite3.connect(DB_PATH)

# ==========================================
# 1. Migrate MIMIC-III CSV files
# ==========================================

tables_to_migrate = [
    {"table": "PATIENTS", "file": "PATIENTS", "index": "subject_id"},
    {"table": "CHARTEVENTS", "file": "CHARTEVENTS", "index": "subject_id"},
    {"table": "LABEVENTS", "file": "LABEVENTS", "index": "subject_id"},
    {"table": "NOTEEVENTS", "file": "NOTEEVENTS", "index": "subject_id"},
    {"table": "D_ITEMS", "file": "D_ITEMS", "index": "itemid"},
    {"table": "D_LABITEMS", "file": "D_LABITEMS", "index": "itemid"},
]

for item in tables_to_migrate:
    table_name = item["table"]
    file_path = MIMIC_DIR / f"{item['file']}.csv"
    
    if file_path.exists():
        print(f"Migrating {table_name} from CSV to SQLite...", end="", flush=True)
        # Use chunksize for large files like CHARTEVENTS
        chunk_iter = pd.read_csv(file_path, chunksize=100000)
        first_chunk = True
        for chunk in chunk_iter:
            chunk.columns = [c.lower() for c in chunk.columns] # lowercase all columns for easier SQL parsing
            if first_chunk:
                chunk.to_sql(table_name, conn, if_exists="replace", index=False)
                first_chunk = False
            else:
                chunk.to_sql(table_name, conn, if_exists="append", index=False)
        print(" DONE.")
        
        # Build index for fast lookup
        idx_col = item['index']
        print(f"  -> Building Index on {idx_col}...")
        conn.execute(f"CREATE INDEX idx_{table_name}_{idx_col} ON {table_name}({idx_col})")
    else:
        print(f"Warning: {file_path} not found. Skipping {table_name}.")

# ==========================================
# 2. Migrate Custom Data JSONs
# ==========================================

print("Migrating Custom Notes JSON to SQLite...", end="", flush=True)
custom_notes_file = DATA_DIR / "custom_notes.json"
conn.execute('''CREATE TABLE IF NOT EXISTS custom_notes
             (subject_id TEXT, note_id TEXT, text_content TEXT, category TEXT, timestamp TEXT, author TEXT, role TEXT)''')

if custom_notes_file.exists():
    with open(custom_notes_file, 'r', encoding='utf-8') as f:
        notes_db = json.load(f)
        for subject_id, notes in notes_db.items():
            for note in notes:
                conn.execute(
                    "INSERT INTO custom_notes VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (subject_id, note.get("id"), note.get("text"), note.get("category"), 
                     note.get("timestamp"), note.get("author"), note.get("role"))
                )
print(" DONE.")
conn.execute("CREATE INDEX idx_custom_notes_subject_id ON custom_notes(subject_id)")

print("Migrating Analysis History JSON to SQLite...", end="", flush=True)
analysis_file = DATA_DIR / "analysis_history.json"
conn.execute('''CREATE TABLE IF NOT EXISTS analysis_history
             (subject_id TEXT PRIMARY KEY, risk_score REAL, anomalies TEXT, recommendations TEXT, timestamp TEXT)''')

if analysis_file.exists():
    with open(analysis_file, 'r', encoding='utf-8') as f:
        history_db = json.load(f)
        for subject_id, ai in history_db.items():
            anomalies_json = json.dumps(ai.get("anomalies", []))
            recommendations_json = json.dumps(ai.get("recommendations", []))
            conn.execute(
                "INSERT INTO analysis_history VALUES (?, ?, ?, ?, ?)",
                (subject_id, ai.get("risk_score"), anomalies_json, recommendations_json, ai.get("timestamp"))
            )
print(" DONE.")

conn.commit()
conn.close()

print("\nDatabase Migration Complete! The application is now fully relational.")
