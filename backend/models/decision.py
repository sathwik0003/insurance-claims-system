from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .claim import ClaimCategory, RejectionReason


class DecisionType(str, Enum):
    APPROVED = "APPROVED"
    PARTIAL = "PARTIAL"
    REJECTED = "REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class LineItemDecision(BaseModel):
    description: str
    claimed_amount: float
    approved_amount: float
    reason: str


class ClaimDecision(BaseModel):
    claim_id: UUID = Field(default_factory=uuid4)
    member_id: str
    claim_category: ClaimCategory
    treatment_date: str
    claimed_amount: float

    decision: DecisionType
    approved_amount: float = 0.0
    rejection_reasons: list[RejectionReason] = []
    line_item_decisions: list[LineItemDecision] = []

    decision_reason: str = ""
    member_message: str = ""
    confidence_score: float = Field(ge=0.0, le=1.0)

    # Financial breakdown
    network_discount_applied: float = 0.0
    copay_deducted: float = 0.0

    # Observability
    component_failures: list[str] = []
    manual_review_recommended: bool = False

    created_at: datetime = Field(default_factory=datetime.utcnow)