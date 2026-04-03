class ClinicalDataIncompleteError(Exception):
    """Raised when a patient record lacks required clinical fields for sepsis analysis."""


class AIProcessingTimeout(Exception):
    """Raised when AI analysis does not complete within the allowed processing time."""
