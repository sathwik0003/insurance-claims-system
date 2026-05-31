from __future__ import annotations

from pydantic import BaseModel

from .claim import ClaimCategory, FraudCheckResult, RuleResult
from .decision import ClaimDecision, LineItemDecision
from .document import ParsedDocument, VerifiedDocument
from .trace import ClaimTrace


class DocumentVerificationResult(BaseModel):
    """Output of Agent 1. On failure the pipeline stops here."""
    passed: bool
    verified_documents: list[VerifiedDocument] = []
    error_code: str | None = None
    error_message: str | None = None


class ClaimResponse(BaseModel):
    """Top-level API response for /claims/submit."""
    success: bool
    document_error: DocumentVerificationResult | None = None
    decision: ClaimDecision | None = None
    trace: ClaimTrace | None = None


# ── Eval endpoint models (for running test_cases.json) ────────────────────────

class EvalDocument(BaseModel):
    """A document from test_cases.json — pre-classified, pre-parsed content."""
    file_id: str
    file_name: str = ""
    actual_type: str                    # e.g. "PRESCRIPTION"
    quality: str = "GOOD"
    patient_name_on_doc: str | None = None
    content: dict = {}                  # pre-extracted fields


class EvalClaimInput(BaseModel):
    """Maps directly to a test case from test_cases.json."""
    member_id: str
    policy_id: str = "PLUM_GHI_2024"
    claim_category: ClaimCategory
    treatment_date: str
    claimed_amount: float
    hospital_name: str | None = None
    ytd_claims_amount: float = 0.0
    simulate_component_failure: bool = False
    claims_history: list[dict] = []
    documents: list[EvalDocument] = []