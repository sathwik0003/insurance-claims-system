from __future__ import annotations

import time
import uuid

from models.claim import ClaimSubmission, FraudCheckResult, RejectionReason
from models.decision import ClaimDecision, DecisionType, LineItemDecision
from models.document import ParsedDocument
from models.trace import TraceEntry
from services.rules_engine import RulesOutput

_FAILURE_PENALTY = 0.15


class DecisionAggregatorAgent:
    """
    Agent 4 — Decision Aggregator.

    Combines RulesOutput + FraudCheckResult + document confidence
    into a single ClaimDecision with a confidence score.

    TC011 (graceful degradation): each component_failure reduces
    confidence by 0.15 and sets manual_review_recommended=True.

    Contract:
      Input : submission, rules_output, fraud_result, parsed_docs, component_failures
      Output: (ClaimDecision, TraceEntry)
      Errors: Never raises.
    """

    def run(
        self,
        submission: ClaimSubmission,
        rules_output: RulesOutput,
        fraud_result: FraudCheckResult,
        parsed_docs: list[ParsedDocument],
        component_failures: list[str],
    ) -> tuple[ClaimDecision, TraceEntry]:
        started = time.monotonic()

        failed_rules = [r for r in rules_output.rules if not r.passed]
        # Only rules with explicit rejection_reason are blocking
        blocking_rules = [r for r in failed_rules if r.rejection_reason]
        rejection_reasons = list({r.rejection_reason for r in blocking_rules})

        # ── Determine decision ────────────────────────────────────────────
        if fraud_result.requires_manual_review:
            decision = DecisionType.MANUAL_REVIEW
            approved_amount = 0.0
            reason = (
                "Routed to manual review — fraud signals: "
                + "; ".join(s.description for s in fraud_result.signals)
            )

        elif RejectionReason.EXCLUDED_CONDITION in rejection_reasons:
            decision = DecisionType.REJECTED
            approved_amount = 0.0
            reason = self._join_failures(blocking_rules)

        elif any(r in rejection_reasons for r in [
            RejectionReason.WAITING_PERIOD,
            RejectionReason.PRE_AUTH_MISSING,
            RejectionReason.PER_CLAIM_EXCEEDED,
            RejectionReason.ANNUAL_LIMIT_EXCEEDED,
            RejectionReason.MEMBER_NOT_FOUND,
            RejectionReason.DUPLICATE_CLAIM,
        ]):
            decision = DecisionType.REJECTED
            approved_amount = 0.0
            reason = self._join_failures(blocking_rules)

        elif rules_output.line_items and any(
            lid.approved_amount < lid.claimed_amount
            for lid in rules_output.line_items
        ):
            decision = DecisionType.PARTIAL
            approved_amount = sum(lid.approved_amount for lid in rules_output.line_items)
            reason = self._partial_reason(rules_output.line_items)

        elif blocking_rules:
            decision = DecisionType.REJECTED
            approved_amount = 0.0
            reason = self._join_failures(blocking_rules)

        else:
            decision = DecisionType.APPROVED
            approved_amount = rules_output.net_amount
            reason = self._approval_reason(
                approved_amount, rules_output.network_discount, rules_output.copay_deducted
            )

        # ── Confidence score ──────────────────────────────────────────────
        doc_conf = (
            sum(d.overall_confidence for d in parsed_docs) / len(parsed_docs)
            if parsed_docs else 0.5
        )
        rule_conf = 0.95 if not failed_rules else 0.85
        base_conf = round(doc_conf * 0.3 + rule_conf * 0.7, 3)
        confidence = max(0.1, round(base_conf - len(component_failures) * _FAILURE_PENALTY, 3))

        manual_review = (
            fraud_result.requires_manual_review
            or bool(component_failures)
            or decision == DecisionType.MANUAL_REVIEW
        )

        claim_decision = ClaimDecision(
            claim_id=uuid.uuid4(),
            member_id=submission.member_id,
            claim_category=submission.claim_category,
            treatment_date=submission.treatment_date,
            claimed_amount=submission.claimed_amount,
            decision=decision,
            approved_amount=round(approved_amount, 2),
            rejection_reasons=rejection_reasons,
            line_item_decisions=rules_output.line_items or [],
            decision_reason=reason,
            member_message=self._member_message(decision, reason),
            confidence_score=confidence,
            network_discount_applied=rules_output.network_discount,
            copay_deducted=rules_output.copay_deducted,
            component_failures=component_failures,
            manual_review_recommended=manual_review,
        )

        entry = TraceEntry(
            component="DecisionAggregatorAgent",
            duration_ms=int((time.monotonic() - started) * 1000),
            output_summary={
                "decision": decision.value,
                "approved_amount": approved_amount,
                "confidence": confidence,
                "rejections": [r.value for r in rejection_reasons],
                "manual_review": manual_review,
            },
        )
        return claim_decision, entry

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _join_failures(failed) -> str:
        return " | ".join(r.reason for r in failed)

    @staticmethod
    def _partial_reason(items: list[LineItemDecision]) -> str:
        approved = [i for i in items if i.approved_amount > 0]
        rejected = [i for i in items if i.approved_amount == 0]
        parts = []
        if approved:
            parts.append("Approved: " + ", ".join(
                f"{i.description} ₹{i.approved_amount:,.0f}" for i in approved
            ))
        if rejected:
            parts.append("Rejected: " + ", ".join(
                f"{i.description} ₹{i.claimed_amount:,.0f} — {i.reason}" for i in rejected
            ))
        return " | ".join(parts)

    @staticmethod
    def _approval_reason(approved: float, discount: float, copay: float) -> str:
        parts = [f"Approved ₹{approved:,.2f}."]
        if discount:
            parts.append(f"Network discount: -₹{discount:,.2f}.")
        if copay:
            parts.append(f"Co-pay: -₹{copay:,.2f}.")
        return " ".join(parts)

    @staticmethod
    def _member_message(decision: DecisionType, reason: str) -> str:
        msgs = {
            DecisionType.APPROVED:      f"Your claim has been approved. {reason}",
            DecisionType.PARTIAL:       f"Your claim has been partially approved. {reason}",
            DecisionType.REJECTED:      f"Your claim could not be approved. {reason}",
            DecisionType.MANUAL_REVIEW: (
                "Your claim has been flagged for manual review. "
                "Our team will contact you within 2 business days."
            ),
        }
        return msgs[decision]