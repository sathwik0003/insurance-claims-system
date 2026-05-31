"""
All database read/write operations using raw asyncpg.
No SQLAlchemy ORM — avoids prepared statement conflicts with Supabase pooler.
"""

from __future__ import annotations

import json
from datetime import datetime

import asyncpg

from models.decision import ClaimDecision
from models.document import ParsedDocument
from models.trace import ClaimTrace


# ── Fraud / duplicate checks ──────────────────────────────────────────────────

async def get_ytd_approved_amount(
    conn: asyncpg.Connection, member_id: str, year: int
) -> float:
    val = await conn.fetchval(
        """
        SELECT COALESCE(SUM(approved_amount), 0)
        FROM claims
        WHERE member_id = $1
          AND treatment_date LIKE $2
          AND decision = ANY($3)
        """,
        member_id,
        f"{year}-%",
        ["APPROVED", "PARTIAL"],
    )
    return float(val or 0)


async def get_claims_on_date(
    conn: asyncpg.Connection, member_id: str, treatment_date: str
) -> list[dict]:
    rows = await conn.fetch(
        "SELECT claim_id FROM claims WHERE member_id = $1 AND treatment_date = $2",
        member_id, treatment_date,
    )
    return [dict(r) for r in rows]


async def get_claims_in_month(
    conn: asyncpg.Connection, member_id: str, year: int, month: int
) -> list[dict]:
    rows = await conn.fetch(
        "SELECT claim_id FROM claims WHERE member_id = $1 AND treatment_date LIKE $2",
        member_id, f"{year}-{month:02d}-%",
    )
    return [dict(r) for r in rows]


async def is_duplicate_claim(
    conn: asyncpg.Connection,
    member_id: str,
    treatment_date: str,
    claim_category: str,
) -> bool:
    """
    A duplicate is the same member claiming the same category on the same day
    and the previous claim was not rejected. We intentionally exclude amount
    from this check — minor rounding differences in extracted amounts would
    otherwise allow the same claim through.
    """
    row = await conn.fetchrow(
        """
        SELECT claim_id FROM claims
        WHERE member_id = $1
          AND treatment_date = $2
          AND claim_category = $3
          AND decision != 'REJECTED'
        LIMIT 1
        """,
        member_id, treatment_date, claim_category,
    )
    return row is not None




# ── Write ─────────────────────────────────────────────────────────────────────

async def save_claim(
    conn: asyncpg.Connection,
    decision: ClaimDecision,
    policy_id: str,
    hospital_name: str | None,
    trace: ClaimTrace,
    parsed_docs: list[ParsedDocument],
) -> None:
    claim_id = str(decision.claim_id)
    now = datetime.utcnow()

    await conn.execute(
        """
        INSERT INTO claims (
            claim_id, member_id, policy_id, claim_category,
            treatment_date, claimed_amount, hospital_name,
            decision, approved_amount, confidence_score,
            rejection_reasons, decision_reason, member_message,
            network_discount_applied, copay_deducted,
            manual_review_recommended, component_failures,
            created_at, updated_at
        ) VALUES (
            $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
            $11,$12,$13,$14,$15,$16,$17,$18,$19
        )
        ON CONFLICT (claim_id) DO NOTHING
        """,
        claim_id,
        decision.member_id,
        policy_id,
        decision.claim_category.value,
        decision.treatment_date,
        decision.claimed_amount,
        hospital_name,
        decision.decision.value,
        decision.approved_amount,
        decision.confidence_score,
        [r.value for r in decision.rejection_reasons],   # list → jsonb via codec
        decision.decision_reason,
        decision.member_message,
        decision.network_discount_applied,
        decision.copay_deducted,
        str(decision.manual_review_recommended),
        decision.component_failures,                     # list → jsonb via codec
        now,
        now,
    )

    for doc in parsed_docs:
        await conn.execute(
            """
            INSERT INTO claim_documents (
                id, claim_id, file_name, classified_type,
                quality, extracted_data, overall_confidence, created_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            ON CONFLICT (id) DO NOTHING
            """,
            doc.file_id,
            claim_id,
            doc.file_id,
            doc.document_type.value,
            doc.quality.value,
            doc.model_dump(mode="json"),
            doc.overall_confidence,
            now,
        )

    await conn.execute(
        """
        INSERT INTO claim_traces (claim_id, trace_json, created_at)
        VALUES ($1, $2, $3)
        ON CONFLICT (claim_id) DO NOTHING
        """,
        claim_id,
        trace.model_dump(mode="json"),                   # dict → jsonb via codec
        now,
    )


# ── Lookups ───────────────────────────────────────────────────────────────────

async def get_claim_by_id(
    conn: asyncpg.Connection, claim_id: str
) -> tuple[dict, dict | None] | None:
    row = await conn.fetchrow(
        "SELECT * FROM claims WHERE claim_id = $1", claim_id
    )
    if not row:
        return None
    claim = dict(row)

    trace_row = await conn.fetchrow(
        "SELECT trace_json FROM claim_traces WHERE claim_id = $1", claim_id
    )
    trace = dict(trace_row)["trace_json"] if trace_row else None
    return claim, trace


async def get_member_claims(
    conn: asyncpg.Connection, member_id: str, limit: int = 20
) -> list[dict]:
    rows = await conn.fetch(
        """
        SELECT claim_id, treatment_date, claim_category,
               claimed_amount, decision, approved_amount, created_at
        FROM claims
        WHERE member_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        member_id, limit,
    )
    return [dict(r) for r in rows]