from pathlib import Path
import asyncio
import logging

from fastapi import FastAPI, HTTPException, Request, Path as FastApiPath, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import schemas
from app.auth import (
    AuthResponse,
    AuthUser,
    LoginRequest,
    authenticate_user,
    create_access_token,
    get_current_user,
    init_auth_db,
)
from app.data_loader import get_available_subject_ids, get_mimic_patient
from app.dashboard_loader import get_dashboard_patients, get_enriched_patient
from app.document_ingestion import extract_document_text
from app.email_service import send_family_email
from app.engine import analyze_patient_data
from app.exceptions import AIProcessingTimeout, ClinicalDataIncompleteError
from app.family_communication_service import get_family_communication_provider_status

app = FastAPI(title="OmniKavach — ICU Diagnostic Assistant API")

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
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    """Lightweight backend health endpoint for UI status checks."""
    family_status = get_family_communication_provider_status()
    return {
        "status": "ok",
        "service": "OmniKavach Backend",
        "family_communication": family_status,
    }


@app.on_event("startup")
async def startup_event() -> None:
    init_auth_db()


@app.get("/health")
def health() -> dict:
    return {"status": "online"}


@app.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest) -> AuthResponse:
    user = authenticate_user(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    return AuthResponse(access_token=create_access_token(user), user=user)


@app.get("/auth/me", response_model=AuthUser)
def auth_me(current_user: AuthUser = Depends(get_current_user)) -> AuthUser:
    return current_user


# ============================================================
# Exception Handlers
# ============================================================

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


# ============================================================
# Notes Submission
# ============================================================

class NoteSubmission(schemas.BaseModel):
    text: str
    category: str


class FamilyEmailRequest(schemas.BaseModel):
    recipient_email: str


@app.post("/patients/{patient_id}/notes")
def add_patient_note(
    patient_id: str,
    note: NoteSubmission,
    current_user: AuthUser = Depends(get_current_user),
):
    """Add a new clinical note for a patient."""
    try:
        from app.dashboard_loader import save_custom_note
        save_custom_note(patient_id, note.text, note.category)
        return {"status": "success", "message": "Note saved successfully"}
    except Exception as e:
        logger.error("Failed to save note for patient %s: %s", patient_id, e)
        raise HTTPException(status_code=500, detail="Failed to save note")


@app.delete("/patients/{patient_id}/notes/{note_id}")
def delete_patient_note(
    patient_id: str,
    note_id: str,
    current_user: AuthUser = Depends(get_current_user),
):
    """Delete a user-added note so it no longer influences future analysis."""
    try:
        from app.dashboard_loader import delete_custom_note

        deleted = delete_custom_note(patient_id, note_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Note not found or cannot be deleted.")
        return {"status": "success", "message": "Note deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete note %s for patient %s: %s", note_id, patient_id, e)
        raise HTTPException(status_code=500, detail="Failed to delete note")


@app.post("/patients/{patient_id}/upload")
async def upload_patient_document(
    patient_id: str,
    file: UploadFile = File(...),
    current_user: AuthUser = Depends(get_current_user),
):
    """Upload a report or clinical photo, extract text, and save it as a clinical note."""
    try:
        contents = await file.read()
        extracted_text, category = extract_document_text(file.filename, contents)

        from app.dashboard_loader import save_custom_note
        save_custom_note(
            patient_id, 
            f"[DOCUMENT UPLOAD: {file.filename}]\n\n{extracted_text}", 
            category
        )
        
        return {
            "status": "success", 
            "message": "File parsed and saved successfully",
            "filename": file.filename,
            "category": category
        }
    except Exception as e:
        logger.error("Failed to process uploaded document for patient %s: %s", patient_id, e)
        raise HTTPException(status_code=500, detail=f"Failed to process uploaded file: {str(e)}")


@app.post("/patients/{patient_id}/family-email")
def email_family_update(
    patient_id: int,
    payload: FamilyEmailRequest,
    current_user: AuthUser = Depends(get_current_user),
):
    """Send the latest family-facing communication via email."""
    try:
        enriched = get_enriched_patient(patient_id)
        if not enriched or not enriched.aiSynthesis or not enriched.aiSynthesis.familyCommunication:
            raise HTTPException(
                status_code=400,
                detail="Family communication is not ready yet. Run analysis first.",
            )

        result = send_family_email(
            patient_name=enriched.name,
            recipient_email=payload.recipient_email,
            family_communication=enriched.aiSynthesis.familyCommunication,
        )
        return {
            "status": "success",
            "message": "Family communication email sent successfully.",
            "email_id": result.get("id"),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to send family email for patient %s: %s", patient_id, e)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Dashboard Endpoints (Enriched — for Frontend)
# ============================================================

@app.get("/patients/dashboard", response_model=list[schemas.PatientSummary])
def get_dashboard(current_user: AuthUser = Depends(get_current_user)) -> list[schemas.PatientSummary]:
    """Return enriched patient summaries for the ward dashboard."""
    try:
        return get_dashboard_patients(limit=6)
    except ClinicalDataIncompleteError as exc:
        logger.error("Failed to load dashboard: %s", str(exc))
        raise HTTPException(
            status_code=503,
            detail="MIMIC dataset is not properly configured or accessible"
        ) from exc
    except Exception as exc:
        logger.error("Unexpected error loading dashboard: %s", str(exc), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while loading dashboard data"
        ) from exc


@app.get("/patients/{patient_id}/enriched", response_model=schemas.EnrichedPatient)
def get_patient_enriched(
    patient_id: int = FastApiPath(..., ge=1, le=999999, description="MIMIC subject ID"),
    current_user: AuthUser = Depends(get_current_user),
) -> schemas.EnrichedPatient:
    """Return full enriched patient data for the detail view."""
    logger.info("Requesting enriched data for SUBJECT_ID: %s", patient_id)

    try:
        enriched = get_enriched_patient(patient_id)
    except ClinicalDataIncompleteError as exc:
        logger.error("Data loading error for patient %s: %s", patient_id, str(exc))
        raise HTTPException(
            status_code=503,
            detail="MIMIC dataset is not properly configured or accessible"
        ) from exc
    except Exception as exc:
        logger.error("Unexpected error loading enriched patient %s: %s", patient_id, str(exc), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error while loading patient {patient_id}"
        ) from exc

    if enriched is None:
        raise HTTPException(
            status_code=404,
            detail=f"Patient with SUBJECT_ID {patient_id} not found in MIMIC sources",
        )

    logger.info("Enriched data ready for patient %s — Risk: %s%%", patient_id, enriched.riskScore)
    return enriched


# ============================================================
# Raw MIMIC Endpoints (kept for backward compatibility)
# ============================================================

@app.get("/patients", response_model=list[int])
def get_patients(current_user: AuthUser = Depends(get_current_user)) -> list[int]:
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
def get_patient(
    patient_id: int = FastApiPath(..., ge=1, le=999999, description="MIMIC subject ID (must be positive integer)"),
    current_user: AuthUser = Depends(get_current_user),
) -> schemas.PatientData:
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


# ============================================================
# Analysis Endpoint
# ============================================================

@app.post("/analyze/{patient_id}", response_model=schemas.AnalysisReport)
async def analyze_patient(
    patient_id: int = FastApiPath(..., ge=1, le=999999, description="MIMIC subject ID (must be positive integer)"),
    current_user: AuthUser = Depends(get_current_user),
) -> schemas.AnalysisReport:
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

    # Merge custom notes into the analysis data
    from app.dashboard_loader import _read_custom_notes
    custom_notes_db = _read_custom_notes()
    sid_str = str(patient_id)
    if sid_str in custom_notes_db:
        for cn in custom_notes_db[sid_str]:
            patient_data.clinical_notes.append(schemas.ClinicalNote(
                note_id=cn["id"],
                text_content=cn["text"],
                category=cn["category"]
            ))

    if not patient_data.vital_signs and not patient_data.lab_results and not patient_data.clinical_notes:
        logger.warning("Insufficient data for analysis - patient %s has no vitals, labs, or notes", patient_id)
        raise ClinicalDataIncompleteError(
            f"Patient {patient_id} has no clinical data available for analysis"
        )

    try:
        # TIMEOUT INCREASED TO 20 SECONDS
        analysis_result = await asyncio.wait_for(analyze_patient_data(patient_data), timeout=20)
        
        # Validate analysis result
        if analysis_result is None:
            logger.error("Analysis engine returned None for patient %s", patient_id)
            raise HTTPException(
                status_code=500,
                detail="Analysis engine failed to generate results"
            )
            
        logger.info("Analysis completed for patient %s - Risk Score: %.2f", 
                   patient_id, analysis_result.risk_score)
        
        # PERSIST RESULT
        try:
            from app.dashboard_loader import save_analysis_result
            save_analysis_result(patient_id, analysis_result)
        except Exception as e:
            logger.error("Failed to persist analysis for %s: %s", patient_id, e)

        return analysis_result
        
    except asyncio.TimeoutError as exc:
        logger.error("AI analysis timed out after 20 seconds for patient %s", patient_id)
        raise AIProcessingTimeout(
            f"AI analysis timed out after 20 seconds for patient {patient_id}"
        ) from exc
    except Exception as exc:
        logger.error("Analysis engine error for patient %s: %s", patient_id, str(exc), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Analysis engine encountered an error for patient {patient_id}"
        ) from exc
