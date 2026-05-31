"""
Claims Pipeline Orchestrator.

Two entry points:
  process()      — real submission with file uploads (Agents 1→4 all run)
  process_eval() — test_cases.json submission (Agents 1+2 mocked from pre-parsed content)

Every stage is wrapped in try/except.
Failures append to component_failures; the pipeline continues
with reduced confidence (TC011 behaviour).

Claims Pipeline Orchestrator.

Two entry points:
  process()      — real submission with file uploads (Agents 1→4 all run)
  process_eval() — test_cases.json submission (Agents 1+2 mocked from pre-parsed content)

Every stage is wrapped in try/except.
Failures append to component_failures; the pipeline continues
with reduced confidence (TC011 behaviour).

Claims Pipeline Orchestrator.

Two entry points:
  process()      — real submission with file uploads (Agents 1→4 all run)
  process_eval() — test_cases.json submission (Agents 1+2 mocked from pre-parsed content)

Every stage is wrapped in try/except.
Failures append to component_failures; the pipeline continues
with reduced confidence (TC011 behaviour).
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import date

import asyncpg
from groq import AsyncGroq

from agents.decision_aggregator import DecisionAggregatorAgent
from agents.doc_parser import DocParserAgent
from agents.doc_verifier import DocVerifierAgent
from agents.fraud_detector import FraudDetectorAgent
from config import get_settings
from db.queries import (
    get_claims_in_month,
    get_claims_on_date,
    get_ytd_approved_amount,
    is_duplicate_claim,
    save_claim,
)
from models.api import ClaimResponse, DocumentVerificationResult, EvalClaimInput
from models.claim import ClaimSubmission, FraudCheckResult
from models.decision import ClaimDecision, DecisionType
from models.document import DocumentQuality, DocumentType, LineItem, ParsedDocument, VerifiedDocument
from models.trace import ClaimTrace, TraceEntry
from services.policy_service import get_policy_service
from services.rules_engine import RulesEngine, RulesOutput

logger = logging.getLogger(__name__)


class ClaimsPipeline:
    def __init__(self, db: asyncpg.Connection) -> None:
        s = get_settings()
        groq = AsyncGroq(api_key=s.groq_api_key)
        policy = get_policy_service()  # singleton

        self._db = db
        self._verifier = DocVerifierAgent(groq, policy)
        self._parser = DocParserAgent(groq)
        self._rules = RulesEngine(policy)
        self._fraud = FraudDetectorAgent(policy)
        self._aggregator = DecisionAggregatorAgent()

    # ── Production submission (real file uploads) ─────────────────────────────

    async def process(self, submission: ClaimSubmission) -> ClaimResponse:
        trace = ClaimTrace()
        failures: list[str] = []
        started = time.monotonic()

        # Stage 1: Document Verification
        verification = None
        try:
            verification, entry = await self._verifier.run(submission)
            trace.add(entry)
        except Exception as exc:
            failures.append(f"DocVerifierAgent: {exc}")
            trace.add(TraceEntry(component="DocVerifierAgent", error=str(exc)))
            logger.error("DocVerifierAgent crashed: %s", exc)

        if verification and not verification.passed and verification.error_code != "AGENT_FAILURE":
            return ClaimResponse(success=False, document_error=verification)

        verified_docs = getattr(verification, "verified_documents", [])

        # Stage 2: Document Parsing
        b64_map = {d.file_id: d.content_base64 for d in submission.documents}
        mime_map = {d.file_id: d.mime_type for d in submission.documents}
        parsed_docs: list[ParsedDocument] = []

        try:
            parsed_docs, entry = await self._parser.run(verified_docs, b64_map, mime_map)
            trace.add(entry)
            if entry.error:
                failures.append(f"DocParserAgent(partial): {entry.error}")
        except Exception as exc:
            failures.append(f"DocParserAgent: {exc}")
            trace.add(TraceEntry(component="DocParserAgent", error=str(exc)))

        return await self._run_decision_stages(
            submission, parsed_docs, trace, failures, started
        )

    # ── Eval submission (test_cases.json — no image files) ────────────────────

    async def process_eval(self, inp: EvalClaimInput) -> ClaimResponse:
        trace = ClaimTrace()
        failures: list[str] = []
        started = time.monotonic()

        # Mock Agent 1 — build VerifiedDocuments from actual_type
        verified_docs: list[VerifiedDocument] = []
        for doc in inp.documents:
            try:
                doc_type = DocumentType(doc.actual_type)
            except ValueError:
                doc_type = DocumentType.UNKNOWN
            try:
                quality = DocumentQuality(doc.quality)
            except ValueError:
                quality = DocumentQuality.GOOD

            verified_docs.append(VerifiedDocument(
                file_id=doc.file_id,
                file_name=doc.file_name or doc.file_id,
                classified_type=doc_type,
                quality=quality,
                patient_name_on_doc=doc.patient_name_on_doc,
                classification_confidence=1.0,
            ))

        # ── Check 1: Unreadable documents (TC002) ────────────────────────
        unreadable = [v for v in verified_docs if v.quality == DocumentQuality.UNREADABLE]
        if unreadable:
            names = ", ".join(f"'{d.file_name}'" for d in unreadable)
            return ClaimResponse(
                success=False,
                document_error=DocumentVerificationResult(
                    passed=False,
                    verified_documents=verified_docs,
                    error_code="UNREADABLE_DOCUMENT",
                    error_message=(
                        f"The following document(s) could not be read: {names}. "
                        "Please re-upload a clearer photo with good lighting and all text visible."
                    ),
                ),
            )

        # ── Check 2: Patient name mismatch (TC003) ───────────────────────
        named = [v for v in verified_docs if v.patient_name_on_doc]
        if len(named) >= 2:
            norm = lambda n: " ".join(n.lower().split())
            base_name = norm(named[0].patient_name_on_doc)
            mismatches = [d for d in named[1:] if norm(d.patient_name_on_doc) != base_name]
            if mismatches:
                detail = ", ".join(
                    f"'{d.file_name}' -> {d.patient_name_on_doc}" for d in named
                )
                return ClaimResponse(
                    success=False,
                    document_error=DocumentVerificationResult(
                        passed=False,
                        verified_documents=verified_docs,
                        error_code="PATIENT_MISMATCH",
                        error_message=(
                            f"Documents belong to different patients. "
                            f"Names found: {detail}. "
                            "All documents must be for the same patient."
                        ),
                    ),
                )

        # ── Check 3: Wrong document types (TC001) ────────────────────────
        from services.policy_service import get_policy_service
        policy = get_policy_service()
        required = policy.required_document_types(inp.claim_category)
        provided = [v.classified_type for v in verified_docs]
        missing = [r for r in required if r not in provided]

        if missing:
            missing_str = " and ".join(t.value.replace("_", " ").title() for t in missing)
            return ClaimResponse(
                success=False,
                document_error=DocumentVerificationResult(
                    passed=False,
                    verified_documents=verified_docs,
                    error_code="WRONG_DOCUMENT_TYPE",
                    error_message=(
                        f"Missing required document(s): {missing_str}. "
                        "Please re-upload the correct documents."
                    ),
                ),
            )

        trace.add(TraceEntry(
            component="DocVerifierAgent(eval)",
            output_summary={"passed": True, "mocked": True},
        ))

        # Mock Agent 2 — build ParsedDocuments from content dict
        parsed_docs: list[ParsedDocument] = []
        for doc in inp.documents:
            c = doc.content
            try:
                quality = DocumentQuality(doc.quality)
            except ValueError:
                quality = DocumentQuality.GOOD
            try:
                doc_type = DocumentType(doc.actual_type)
            except ValueError:
                doc_type = DocumentType.UNKNOWN

            line_items = [
                LineItem(description=li["description"], amount=float(li["amount"]))
                for li in (c.get("line_items") or [])
            ]

            parsed_docs.append(ParsedDocument(
                file_id=doc.file_id,
                document_type=doc_type,
                quality=quality,
                patient_name=c.get("patient_name"),
                doctor_name=c.get("doctor_name"),
                doctor_registration=c.get("doctor_registration"),
                hospital_name=c.get("hospital_name"),
                diagnosis=c.get("diagnosis"),
                treatment=c.get("treatment"),
                medicines=c.get("medicines") or [],
                tests_ordered=c.get("tests_ordered") or [],
                line_items=line_items,
                total_amount=c.get("total"),
                field_confidences={"patient_name": 1.0, "diagnosis": 1.0, "total_amount": 1.0},
            ))

        trace.add(TraceEntry(
            component="DocParserAgent(eval)",
            output_summary={"parsed": len(parsed_docs), "mocked": True},
        ))

        # Simulate component failure for TC011
        if inp.simulate_component_failure:
            failures.append("DocParserAgent: simulated failure for TC011")
            trace.add(TraceEntry(
                component="DocParserAgent",
                error="Simulated component failure (TC011)",
            ))

        # Build submission object for downstream stages
        submission = ClaimSubmission(
            member_id=inp.member_id,
            policy_id=inp.policy_id,
            claim_category=inp.claim_category,
            treatment_date=inp.treatment_date,
            claimed_amount=inp.claimed_amount,
            hospital_name=inp.hospital_name,
        )

        return await self._run_decision_stages(
            submission, parsed_docs, trace, failures, started,
            ytd_override=inp.ytd_claims_amount,
            same_day_override=len(inp.claims_history),
            monthly_override=len(inp.claims_history),
        )

    # ── Shared decision stages (Stages 3–6) ──────────────────────────────────

    async def _run_decision_stages(
        self,
        submission: ClaimSubmission,
        parsed_docs: list[ParsedDocument],
        trace: ClaimTrace,
        failures: list[str],
        started: float,
        ytd_override: float | None = None,
        same_day_override: int | None = None,
        monthly_override: int | None = None,
    ) -> ClaimResponse:
        t_str = submission.treatment_date
        t_date = date.fromisoformat(t_str)

        # Stage 3: DB lookups
        ytd = ytd_override if ytd_override is not None else 0.0
        same_day_count = same_day_override if same_day_override is not None else 0
        monthly_count = monthly_override if monthly_override is not None else 0
        duplicate = False

        if ytd_override is None:  # only query DB for real submissions
            try:
                ytd = await get_ytd_approved_amount(self._db, submission.member_id, t_date.year)
                same_day = await get_claims_on_date(self._db, submission.member_id, t_str)
                same_day_count = len(same_day)
                monthly = await get_claims_in_month(
                    self._db, submission.member_id, t_date.year, t_date.month
                )
                monthly_count = len(monthly)
                duplicate = await is_duplicate_claim(
                    self._db, submission.member_id, t_str,
                    submission.claimed_amount, submission.claim_category.value,
                )
                trace.add(TraceEntry(
                    component="DBLookup",
                    output_summary={
                        "ytd_approved": ytd, "same_day": same_day_count,
                        "monthly": monthly_count, "is_duplicate": duplicate,
                    },
                ))
            except Exception as exc:
                failures.append(f"DBLookup: {exc}")
                trace.add(TraceEntry(component="DBLookup", error=str(exc)))

        # Stage 4: Rules Engine
        rules_output = RulesOutput(rules=[], line_items=[], net_amount=submission.claimed_amount,
                                   network_discount=0.0, copay_deducted=0.0,
                                   is_network_hospital=False,
                                   trace=TraceEntry(component="RulesEngine"))
        try:
            rules_output = self._rules.run(
                member_id=submission.member_id,
                claim_category=submission.claim_category,
                treatment_date=submission.treatment_date,
                claimed_amount=submission.claimed_amount,
                hospital_name=submission.hospital_name,
                parsed_docs=parsed_docs,
                ytd_approved=ytd,
                is_duplicate=duplicate,
            )
            trace.add(rules_output.trace)
        except Exception as exc:
            failures.append(f"RulesEngine: {exc}")
            trace.add(TraceEntry(component="RulesEngine", error=str(exc)))

        # Stage 5: Fraud Detection
        # Pass member info so fraud agent can check new-member patterns
        member_info = get_policy_service().get_member(submission.member_id)
        fraud_result = FraudCheckResult()
        try:
            fraud_result, entry = self._fraud.run(
                submission, member_info, parsed_docs, same_day_count, monthly_count
            )
            trace.add(entry)
        except Exception as exc:
            failures.append(f"FraudDetectorAgent: {exc}")
            trace.add(TraceEntry(component="FraudDetectorAgent", error=str(exc)))

        # Stage 6: Decision Aggregator
        decision: ClaimDecision
        try:
            decision, entry = self._aggregator.run(
                submission, rules_output, fraud_result, parsed_docs, failures
            )
            trace.add(entry)
        except Exception as exc:
            failures.append(f"DecisionAggregatorAgent: {exc}")
            decision = ClaimDecision(
                claim_id=uuid.uuid4(),
                member_id=submission.member_id,
                claim_category=submission.claim_category,
                treatment_date=submission.treatment_date,
                claimed_amount=submission.claimed_amount,
                decision=DecisionType.MANUAL_REVIEW,
                decision_reason=f"Pipeline failure — manual review: {exc}",
                member_message="Your claim has been routed to manual review due to a system issue.",
                confidence_score=0.1,
                component_failures=failures,
                manual_review_recommended=True,
            )
            trace.add(TraceEntry(component="DecisionAggregatorAgent", error=str(exc)))

        trace.claim_id = decision.claim_id
        trace.total_duration_ms = int((time.monotonic() - started) * 1000)

        # Persist (non-blocking on failure)
        try:
            await save_claim(
                self._db, decision,
                submission.policy_id, submission.hospital_name,
                trace, parsed_docs,
            )
        except Exception as exc:
            logger.warning("Failed to persist claim %s: %s", decision.claim_id, exc)

        return ClaimResponse(success=True, decision=decision, trace=trace)