from typing import List, Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime
import re


class LabResult(BaseModel):
    """Laboratory test result from MIMIC-III data."""
    
    item_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Laboratory item identifier (e.g., 'Lactate', 'Glucose')",
        example="Lactate"
    )
    value: float = Field(
        ...,
        ge=-1000.0,
        le=10000.0,
        description="Numerical value of the lab result",
        example=3.5
    )
    unit: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Unit of measurement for the lab value",
        example="mmol/L"
    )
    timestamp: datetime = Field(
        ...,
        description="Timestamp when the lab result was recorded",
        example="2024-01-15T10:30:00Z"
    )
    
    @validator('item_id')
    def validate_item_id(cls, v):
        if not re.match(r'^[a-zA-Z0-9_\-\s]+$', v):
            raise ValueError('Item ID contains invalid characters')
        return v.strip()
    
    @validator('unit')
    def validate_unit(cls, v):
        if not re.match(r'^[a-zA-Z0-9_\-\/\s%°µ]+$', v):
            raise ValueError('Unit contains invalid characters')
        return v.strip()


class VitalSign(BaseModel):
    """Vital sign measurement from patient monitoring."""
    
    type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Type of vital sign being measured",
        example="Heart Rate"
    )
    value: float = Field(
        ...,
        ge=0.0,
        le=500.0,
        description="Numerical value of the vital sign",
        example=92.5
    )
    timestamp: datetime = Field(
        ...,
        description="Timestamp when the vital sign was recorded",
        example="2024-01-15T10:30:00Z"
    )
    
    @validator('type')
    def validate_type(cls, v):
        if not re.match(r'^[a-zA-Z0-9_\-\s()]+$', v):
            raise ValueError('Vital sign type contains invalid characters')
        return v.strip()


class ClinicalNote(BaseModel):
    """Clinical or nursing note from patient record."""
    
    note_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Unique identifier for the clinical note",
        example="NOTE_12345"
    )
    text_content: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Full text content of the clinical note",
        example="Patient presents with signs of infection and elevated lactate levels."
    )
    category: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Category or type of note",
        example="Nursing"
    )
    
    @validator('note_id')
    def validate_note_id(cls, v):
        if not re.match(r'^[a-zA-Z0-9_\-]+$', v):
            raise ValueError('Note ID contains invalid characters')
        return v.strip()
    
    @validator('text_content')
    def validate_text_content(cls, v):
        # Basic sanitization to prevent script injection
        dangerous_patterns = ['<script', 'javascript:', 'onload=', 'onerror=']
        content_lower = v.lower()
        for pattern in dangerous_patterns:
            if pattern in content_lower:
                raise ValueError('Text content contains potentially dangerous content')
        return v.strip()
    
    @validator('category')
    def validate_category(cls, v):
        if not re.match(r'^[a-zA-Z0-9_\-\s]+$', v):
            raise ValueError('Category contains invalid characters')
        return v.strip()


class PatientData(BaseModel):
    """Container model for a patient's clinical data."""
    
    lab_results: List[LabResult] = Field(
        default_factory=list,
        description="List of laboratory test results",
        example=[]
    )
    vital_signs: List[VitalSign] = Field(
        default_factory=list,
        description="List of vital sign measurements",
        example=[]
    )
    clinical_notes: List[ClinicalNote] = Field(
        default_factory=list,
        description="List of clinical notes",
        example=[]
    )


class AnalysisReport(BaseModel):
    """AI-generated analysis report for sepsis risk assessment."""
    
    risk_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Sepsis risk score ranging from 0.0 (no risk) to 1.0 (critical risk)",
        example=0.78
    )
    detected_anomalies: List[str] = Field(
        default_factory=list,
        description="List of detected clinical anomalies",
        example=["Elevated Lactate", "Tachycardia", "Fever"]
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Clinical recommendations based on the analysis",
        example=["Consider blood culture", "Monitor lactate trends", "Review antibiotic coverage"]
    )
    safety_disclaimer: str = Field(
        default="This is a decision-support tool only. Clinical judgment and direct patient assessment take priority.",
        description="Important safety disclaimer for clinical use",
        example="This is a decision-support tool only. Clinical judgment and direct patient assessment take priority."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "risk_score": 0.78,
                "detected_anomalies": ["Elevated Lactate", "Tachycardia"],
                "recommendations": ["Monitor vitals", "Consider labs"],
                "safety_disclaimer": "This is a decision-support tool only. Clinical judgment and direct patient assessment take priority."
            }
        }
