from app import schemas


async def analyze_patient_data(data: schemas.PatientData) -> schemas.AnalysisReport:
    """
    Heuristic placeholder for sepsis risk until the full AI pipeline is integrated.
    
    This function provides a basic rule-based analysis for sepsis risk assessment
    using key clinical indicators:
    - Elevated lactate (> 2.0 mmol/L)
    - Low Mean Arterial Pressure (MAP < 65 mmHg)
    
    Args:
        data: PatientData containing lab results, vital signs, and clinical notes
        
    Returns:
        AnalysisReport with risk score, detected anomalies, and clinical recommendations
        
    Note:
        This is a temporary implementation pending integration of the full AI pipeline.
        The current logic provides a foundation for testing the API infrastructure.
    """
    has_high_lactate = any(
        lab.item_id.lower().find("lactate") != -1 and lab.value > 2.0
        for lab in data.lab_results
    )
    has_low_map = any(
        ("map" in vital.type.lower() or "mean arterial pressure" in vital.type.lower())
        and vital.value < 65
        for vital in data.vital_signs
    )

    if has_high_lactate or has_low_map:
        anomalies = []
        if has_high_lactate:
            anomalies.append("Elevated Lactate (> 2.0)")
        if has_low_map:
            anomalies.append("Low Mean Arterial Pressure (MAP < 65)")
        return schemas.AnalysisReport(
            risk_score=0.85,
            detected_anomalies=anomalies,
            recommendations=[
                "Escalate to urgent sepsis protocol review",
                "Repeat lactate and continuous hemodynamic monitoring",
            ],
        )

    return schemas.AnalysisReport(
        risk_score=0.15,
        detected_anomalies=["No high-risk hemodynamic or lactate triggers detected"],
        recommendations=["Continue standard monitoring and reassessment"],
    )
