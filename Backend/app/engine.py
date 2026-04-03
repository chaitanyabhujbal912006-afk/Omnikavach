import json
import logging
from app import schemas
from src.agents import run_chief_agent # YOUR AI BRAIN

logger = logging.getLogger(__name__)

async def analyze_patient_data(data: schemas.PatientData) -> schemas.AnalysisReport:
    logger.info("Sending data to AI Brain...")
    
    notes_text = "\n".join([note.text for note in data.clinical_notes])
    labs_text = "\n".join([f"{lab.timestamp}: {lab.itemid} - {lab.value}" for lab in data.lab_results])
    
    # Assuming ITEMID 51301 is WBC
    wbc_array = [float(lab.value) for lab in data.lab_results if lab.itemid == 51301]
    
    # Call your AI
    ai_json_response = run_chief_agent(notes_text, labs_text, wbc_array)
    
    try:
        report_dict = json.loads(ai_json_response)
        return schemas.AnalysisReport(
            risk_score=0.85 if report_dict.get("safety_caveat") else 0.4,
            detected_anomalies=report_dict.get("key_risks", []),
            recommendations=[report_dict.get("timeline_summary", "")]
        )
    except Exception as e:
        logger.error(f"Failed to parse AI output: {e}")
        return schemas.AnalysisReport(
            risk_score=0.0,
            detected_anomalies=["AI Output Error"],
            recommendations=["Check server logs"]
        )