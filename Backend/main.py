from pathlib import Path
import asyncio
import logging

from fastapi import FastAPI, HTTPException, Request, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import schemas
from app.data_loader import get_available_subject_ids, get_mimic_patient
from app.engine import analyze_patient_data
from app.exceptions import AIProcessingTimeout, ClinicalDataIncompleteError

app = FastAPI()

# Configure logging
LOG_FILE = Path(__file__).resolve().parent / "server_errors.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "online"}


@app.exception_handler(ClinicalDataIncompleteError)
async def clinical_data_incomplete_handler(
    request: Request, exc: ClinicalDataIncompleteError
) -> JSONResponse:
    logger.error(
        "ClinicalDataIncompleteError on %s: %s", request.url.path, str(exc), exc_info=True
    )
    return JSONResponse(
        status_code=422,
        content={
            "error": "Incomplete Data",
            "detail": "The patient record is missing vital fields required for Sepsis analysis.",
        },
    )


@app.exception_handler(AIProcessingTimeout)
async def ai_processing_timeout_handler(
    request: Request, exc: AIProcessingTimeout
) -> JSONResponse:
    logger.error("AIProcessingTimeout on %s: %s", request.url.path, str(exc), exc_info=True)
    fallback_report = schemas.AnalysisReport(
        risk_score=0.0,
        detected_anomalies=["AI processing exceeded clinical response threshold"],
        recommendations=[
            "Repeat analysis request",
            "Escalate to bedside clinical assessment immediately",
        ],
    )
    return JSONResponse(status_code=504, content=fallback_report.model_dump())


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception on %s: %s", request.url.path, str(exc), exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected system error occurred. Please contact the ICU technical team.",
        },
    )


@app.get("/patients", response_model=list[int])
def get_patients() -> list[int]:
    """Return available subject IDs from the MIMIC dataset."""
    try:
        return get_available_subject_ids()
    except ClinicalDataIncompleteError as exc:
        logger.error("Failed to load patient list: %s", str(exc))
        raise HTTPException(
            status_code=503,
            detail="MIMIC dataset is not properly configured or accessible"
        ) from exc
    except Exception as exc:
        logger.error("Unexpected error loading patients: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while loading patient data"
        ) from exc


@app.get("/patients/{patient_id}", response_model=schemas.PatientData)
def get_patient(patient_id: int = Path(..., ge=1, le=999999, description="MIMIC subject ID (must be positive integer)")) -> schemas.PatientData:
    """Return full patient data loaded from MIMIC files for a specific subject."""
    logger.info("Requesting patient data for SUBJECT_ID: %s", patient_id)
    
    try:
        patient_data = get_mimic_patient(patient_id)
    except ClinicalDataIncompleteError as exc:
        logger.error("Data loading error for patient %s: %s", patient_id, str(exc))
        raise HTTPException(
            status_code=503,
            detail="MIMIC dataset is not properly configured or accessible"
        ) from exc
    except Exception as exc:
        logger.error("Unexpected error loading patient %s: %s", patient_id, str(exc), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while loading patient {patient_id}"
        ) from exc

    if (
        len(patient_data.lab_results) == 0
        and len(patient_data.vital_signs) == 0
        and len(patient_data.clinical_notes) == 0
    ):
        raise HTTPException(
            status_code=404,
            detail=f"Patient with SUBJECT_ID {patient_id} not found in MIMIC sources",
        )

    logger.info("Successfully loaded patient %s: %d labs, %d vitals, %d notes", 
                patient_id, len(patient_data.lab_results), 
                len(patient_data.vital_signs), len(patient_data.clinical_notes))
    return patient_data


@app.post("/analyze/{patient_id}", response_model=schemas.AnalysisReport)
async def analyze_patient(patient_id: int = Path(..., ge=1, le=999999, description="MIMIC subject ID (must be positive integer)")) -> schemas.AnalysisReport:
    """Load MIMIC patient data and run the analysis engine."""
    logger.info("Risk Analysis requested for patient SUBJECT_ID: %s", patient_id)

    try:
        patient_data = get_mimic_patient(patient_id)
    except ClinicalDataIncompleteError as exc:
        logger.error("Data loading error for patient analysis %s: %s", patient_id, str(exc))
        raise HTTPException(
            status_code=503,
            detail="MIMIC dataset is not properly configured or accessible"
        ) from exc
    except Exception as exc:
        logger.error("Unexpected error loading patient for analysis %s: %s", patient_id, str(exc), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while loading patient {patient_id} for analysis"
        ) from exc

    if not patient_data.vital_signs or not patient_data.lab_results:
        logger.warning("Insufficient data for analysis - patient %s has %d vitals and %d labs", 
                      patient_id, len(patient_data.vital_signs), len(patient_data.lab_results))
        raise ClinicalDataIncompleteError(
            f"Patient {patient_id} is missing vital signs or laboratory results"
        )

    try:
        analysis_result = await asyncio.wait_for(analyze_patient_data(patient_data), timeout=5)
        
        # Validate analysis result
        if analysis_result is None:
            logger.error("Analysis engine returned None for patient %s", patient_id)
            raise HTTPException(
                status_code=500,
                detail="Analysis engine failed to generate results"
            )
            
        logger.info("Analysis completed for patient %s - Risk Score: %.2f", 
                   patient_id, analysis_result.risk_score)
        return analysis_result
        
    except asyncio.TimeoutError as exc:
        logger.error("AI analysis timed out after 5 seconds for patient %s", patient_id)
        raise AIProcessingTimeout(
            f"AI analysis timed out after 5 seconds for patient {patient_id}"
        ) from exc
    except Exception as exc:
        logger.error("Analysis engine error for patient %s: %s", patient_id, str(exc), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Analysis engine encountered an error for patient {patient_id}"
        ) from exc
