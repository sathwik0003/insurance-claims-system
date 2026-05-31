from __future__ import annotations

import time
from datetime import date

from models.claim import ClaimSubmission, FraudCheckResult, FraudSignal
from models.document import ParsedDocument
from models.trace import TraceEntry
from services.policy_service import PolicyService


class FraudDetectorAgent:
    """
    Agent 3 — Fraud Detection.

    Checks behavioural patterns (from DB history) and document authenticity
    (from LLM extraction) against thresholds in policy_terms.json.

    Inputs:
      - submission          : the claim being made
      - member_info         : member's policy details (join date, sum insured, plan)
      - parsed_docs         : LLM-extracted document data including authenticity flags
      - same_day_count      : # existing claims on same treatment date (from DB)
      - monthly_count       : # claims this month (from DB)

    Never auto-rejects — always routes to MANUAL_REVIEW.
    Fraud score 0.0–1.0 aggregated from all signals.
    """

    def __init__(self, policy: PolicyService) -> None:
        self._policy = policy

    def run(
        self,
        submission: ClaimSubmission,
        member_info: dict | None,
        parsed_docs: list[ParsedDocument],
        same_day_count: int,
        monthly_count: int,
    ) -> tuple[FraudCheckResult, TraceEntry]:
        started = time.monotonic()
        thresholds = self._policy.fraud_thresholds()
        signals: list[FraudSignal] = []

        # ── Signal 1: Same-day claims ──────────────────────────────────────
        # Policy: same_day_claims_limit = 2
        # If member already has >= limit claims today, this one is suspicious.
        # TC009: EMP008 has 3 claims on 2024-10-30 → 4th triggers MANUAL_REVIEW
        same_day_limit = thresholds.get("same_day_claims_limit", 2)
        if same_day_count >= same_day_limit:
            signals.append(FraudSignal(
                signal_type="SAME_DAY_CLAIMS",
                description=(
                    f"Member already has {same_day_count} claim(s) on the same date "
                    f"(policy limit: {same_day_limit}). "
                    f"Submitting a {same_day_count + 1}th claim on the same day is unusual."
                ),
                severity=0.75,
            ))

        # ── Signal 2: Monthly claims volume ───────────────────────────────
        # Policy: monthly_claims_limit = 6
        monthly_limit = thresholds.get("monthly_claims_limit", 6)
        if monthly_count >= monthly_limit:
            signals.append(FraudSignal(
                signal_type="HIGH_MONTHLY_FREQUENCY",
                description=(
                    f"Member has submitted {monthly_count} claims this month "
                    f"(limit: {monthly_limit}). High-frequency claiming warrants review."
                ),
                severity=0.55,
            ))

        # ── Signal 3: High-value claim ─────────────────────────────────────
        # Policy: high_value_claim_threshold = 25000
        hv_threshold = thresholds.get("high_value_claim_threshold", 25000)
        if submission.claimed_amount >= hv_threshold:
            signals.append(FraudSignal(
                signal_type="HIGH_VALUE_CLAIM",
                description=(
                    f"Claimed amount ₹{submission.claimed_amount:,.0f} meets or exceeds "
                    f"the high-value threshold ₹{hv_threshold:,.0f}. Requires human verification."
                ),
                severity=0.45,
            ))

        # ── Signal 4: New member, large claim ─────────────────────────────
        # A member who just joined and immediately files a large claim is a
        # common fraud pattern — buy insurance, claim immediately.
        if member_info:
            join_date = date.fromisoformat(member_info.get("join_date", "2000-01-01"))
            t_date = date.fromisoformat(submission.treatment_date)
            days_since_join = (t_date - join_date).days
            if days_since_join < 60 and submission.claimed_amount > 5000:
                signals.append(FraudSignal(
                    signal_type="NEW_MEMBER_LARGE_CLAIM",
                    description=(
                        f"Member joined {days_since_join} days ago and is claiming "
                        f"₹{submission.claimed_amount:,.0f}. New members with large claims "
                        "warrant additional scrutiny."
                    ),
                    severity=0.5,
                ))

        # ── Signal 5: Document authenticity from LLM ──────────────────────
        # Agent 2 (DocParser) explicitly checks stamps, amounts, fonts, etc.
        # and returns a suspicion_level for each document.
        # We surface those findings here as fraud signals.
        for doc in parsed_docs:
            lvl = doc.authenticity_suspicion
            if lvl in ("medium", "high"):
                severity = 0.85 if lvl == "high" else 0.60
                flags_str = (
                    "; ".join(doc.authenticity_flags)
                    if doc.authenticity_flags
                    else "unspecified issues"
                )
                signals.append(FraudSignal(
                    signal_type="DOCUMENT_AUTHENTICITY",
                    description=(
                        f"Document '{doc.file_id}' flagged as suspicious (level: {lvl}). "
                        f"Issues: {flags_str}. "
                        f"LLM assessment: {doc.authenticity_notes[:120] if doc.authenticity_notes else 'see extraction notes'}"
                    ),
                    severity=severity,
                ))
            elif lvl == "low":
                # Low suspicion: add to signal list with low severity (informational)
                signals.append(FraudSignal(
                    signal_type="DOCUMENT_MINOR_CONCERN",
                    description=(
                        f"Document '{doc.file_id}' has minor concerns (level: low). "
                        f"{doc.authenticity_notes[:100] if doc.authenticity_notes else ''}"
                    ),
                    severity=0.2,
                ))

        # ── Aggregate fraud score ─────────────────────────────────────────
        # Score = weighted combination of max severity and average severity.
        # This prevents one low signal from pushing score too high,
        # and one high signal alone from being too dominant.
        fraud_score = 0.0
        if signals:
            max_sev = max(s.severity for s in signals)
            avg_sev = sum(s.severity for s in signals) / len(signals)
            fraud_score = round(0.6 * max_sev + 0.4 * avg_sev, 3)

        # ── Manual review decision ────────────────────────────────────────
        review_threshold = thresholds.get("fraud_score_manual_review_threshold", 0.80)
        auto_above = thresholds.get("auto_manual_review_above", 25000)

        requires_manual = (
            # Explicit same-day breach → always manual (TC009)
            any(s.signal_type == "SAME_DAY_CLAIMS" for s in signals)
            # High document authenticity concern → always manual
            or any(s.signal_type == "DOCUMENT_AUTHENTICITY" and s.severity >= 0.85 for s in signals)
            # Overall fraud score crosses threshold
            or fraud_score >= review_threshold
            # Amount always triggers manual above auto_above threshold
            or submission.claimed_amount >= auto_above
        )

        result = FraudCheckResult(
            fraud_score=fraud_score,
            signals=signals,
            requires_manual_review=requires_manual,
        )

        entry = TraceEntry(
            component="FraudDetectorAgent",
            duration_ms=int((time.monotonic() - started) * 1000),
            input_summary={
                "member_id": submission.member_id,
                "amount": submission.claimed_amount,
                "same_day_claims": same_day_count,
                "monthly_claims": monthly_count,
                "member_join_date": member_info.get("join_date") if member_info else None,
                "docs_checked": len(parsed_docs),
            },
            output_summary={
                "fraud_score": fraud_score,
                "signals": [
                    {"type": s.signal_type, "severity": s.severity, "detail": s.description}
                    for s in signals
                ],
                "manual_review": requires_manual,
            },
        )
        return result, entry