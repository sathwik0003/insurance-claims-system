from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    PRESCRIPTION = "PRESCRIPTION"
    HOSPITAL_BILL = "HOSPITAL_BILL"
    LAB_REPORT = "LAB_REPORT"
    DIAGNOSTIC_REPORT = "DIAGNOSTIC_REPORT"   # Groq sometimes returns this
    PHARMACY_BILL = "PHARMACY_BILL"
    DENTAL_REPORT = "DENTAL_REPORT"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    UNKNOWN = "UNKNOWN"


class DocumentQuality(str, Enum):
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    UNREADABLE = "UNREADABLE"


class UploadedDocument(BaseModel):
    file_id: str
    file_name: str
    content_base64: str | None = None
    mime_type: str = "image/jpeg"


class VerifiedDocument(BaseModel):
    file_id: str
    file_name: str
    classified_type: DocumentType
    quality: DocumentQuality
    patient_name_on_doc: str | None = None
    classification_confidence: float = Field(ge=0.0, le=1.0)
    classification_reasoning: str = ""


class LineItem(BaseModel):
    description: str
    amount: float


class ParsedDocument(BaseModel):
    file_id: str
    document_type: DocumentType
    quality: DocumentQuality

    patient_name: str | None = None
    doctor_name: str | None = None
    doctor_registration: str | None = None
    hospital_name: str | None = None
    document_date: date | None = None

    diagnosis: str | None = None
    treatment: str | None = None
    medicines: list[str] = []
    tests_ordered: list[str] = []

    line_items: list[LineItem] = []
    total_amount: float | None = None
    gst_amount: float = 0.0

    field_confidences: dict[str, float] = {}
    extraction_notes: str = ""

    # Authenticity flags from LLM
    authenticity_genuine: bool = True
    authenticity_suspicion: str = "none"   # none / low / medium / high
    authenticity_flags: list[str] = []
    authenticity_notes: str = ""

    @property
    def overall_confidence(self) -> float:
        if not self.field_confidences:
            return 0.5
        return round(sum(self.field_confidences.values()) / len(self.field_confidences), 3)