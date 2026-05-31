from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .document import UploadedDocument


class ClaimCategory(str, Enum):
    CONSULTATION = "CONSULTATION"
    DIAGNOSTIC = "DIAGNOSTIC"
    PHARMACY = "PHARMACY"
    DENTAL = "DENTAL"
    VISION = "VISION"
    ALTERNATIVE_MEDICINE = "ALTERNATIVE_MEDICINE"


class RejectionReason(str, Enum):
    WAITING_PERIOD = "WAITING_PERIOD"
    PRE_AUTH_MISSING = "PRE_AUTH_MISSING"
    PER_CLAIM_EXCEEDED = "PER_CLAIM_EXCEEDED"
    SUB_LIMIT_EXCEEDED = "SUB_LIMIT_EXCEEDED"
    ANNUAL_LIMIT_EXCEEDED = "ANNUAL_LIMIT_EXCEEDED"
    EXCLUDED_CONDITION = "EXCLUDED_CONDITION"
    EXCLUDED_PROCEDURE = "EXCLUDED_PROCEDURE"
    SUBMISSION_DEADLINE_MISSED = "SUBMISSION_DEADLINE_MISSED"
    MEMBER_NOT_FOUND = "MEMBER_NOT_FOUND"
    DUPLICATE_CLAIM = "DUPLICATE_CLAIM"


class ClaimSubmission(BaseModel):
    member_id: str
    policy_id: str = "PLUM_GHI_2024"
    claim_category: ClaimCategory
    treatment_date: str | None = None   # Optional — extracted from documents if not provided
    claimed_amount: float = Field(gt=0)
    hospital_name: str | None = None
    documents: list[UploadedDocument] = []


class RuleResult(BaseModel):
    rule_name: str
    passed: bool
    reason: str
    rejection_reason: RejectionReason | None = None


class FraudSignal(BaseModel):
    signal_type: str
    description: str
    severity: float = Field(ge=0.0, le=1.0)


class FraudCheckResult(BaseModel):
    fraud_score: float = Field(default=0.0, ge=0.0, le=1.0)
    signals: list[FraudSignal] = []
    requires_manual_review: bool = False