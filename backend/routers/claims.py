from __future__ import annotations

import base64
import logging

import asyncpg
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from db.queries import get_claim_by_id, get_member_claims
from db.session import get_conn
from models.api import ClaimResponse, EvalClaimInput
from models.claim import ClaimCategory, ClaimSubmission
from models.document import UploadedDocument
from pipeline import ClaimsPipeline

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/claims", tags=["claims"])


# ── Submit (multipart file upload) ────────────────────────────────────────────

@router.post("/submit", response_model=ClaimResponse)
async def submit_claim(
    member_id:      str = Form(...),
    claim_category: str = Form(...),
    treatment_date: str | None = Form(None),   # optional — extracted from docs if omitted
    claimed_amount: float = Form(...),
    hospital_name:  str | None = Form(None),
    policy_id:      str = Form("PLUM_GHI_2024"),
    files: list[UploadFile] = File(...),
    conn: asyncpg.Connection = Depends(get_conn),
) -> ClaimResponse:
    try:
        category = ClaimCategory(claim_category.upper())
    except ValueError:
        raise HTTPException(422, f"Invalid claim_category: {claim_category}")

    docs: list[UploadedDocument] = []
    for f in files:
        raw = await f.read()
        mime = f.content_type or "image/jpeg"
        filename = f.filename or f"file_{len(docs)}"

        # PDF → PNG (Groq vision only accepts images)
        if mime == "application/pdf" or filename.lower().endswith(".pdf"):
            try:
                import fitz
                pdf = fitz.open(stream=raw, filetype="pdf")
                pix = pdf[0].get_pixmap(dpi=150)
                raw = pix.tobytes("png")
                mime = "image/png"
                filename = filename.replace(".pdf", ".png")
                pdf.close()
            except ImportError:
                raise HTTPException(
                    422,
                    "PDF support requires pymupdf: pip install pymupdf. "
                    "Alternatively upload a JPEG or PNG photo.",
                )
            except Exception as exc:
                raise HTTPException(422, f"Could not read PDF '{filename}': {exc}")

        docs.append(UploadedDocument(
            file_id=filename,
            file_name=filename,
            content_base64=base64.b64encode(raw).decode(),
            mime_type=mime,
        ))

    submission = ClaimSubmission(
        member_id=member_id,
        policy_id=policy_id,
        claim_category=category,
        treatment_date=treatment_date,
        claimed_amount=claimed_amount,
        hospital_name=hospital_name,
        documents=docs,
    )

    return await ClaimsPipeline(conn).process(submission)


# ── Eval (JSON with pre-parsed content) ───────────────────────────────────────

@router.post("/eval", response_model=ClaimResponse)
async def eval_claim(
    inp: EvalClaimInput,
    conn: asyncpg.Connection = Depends(get_conn),
) -> ClaimResponse:
    return await ClaimsPipeline(conn).process_eval(inp)


# ── GET a specific claim ──────────────────────────────────────────────────────

@router.get("/{claim_id}")
async def get_claim(
    claim_id: str,
    conn: asyncpg.Connection = Depends(get_conn),
):
    result = await get_claim_by_id(conn, claim_id)
    if not result:
        raise HTTPException(404, "Claim not found")

    claim, trace = result
    return {
        "claim": {
            "claim_id":                  claim["claim_id"],
            "member_id":                 claim["member_id"],
            "claim_category":            claim["claim_category"],
            "treatment_date":            claim["treatment_date"],
            "claimed_amount":            claim["claimed_amount"],
            "decision":                  claim["decision"],
            "approved_amount":           claim["approved_amount"],
            "confidence_score":          claim["confidence_score"],
            "rejection_reasons":         claim["rejection_reasons"],
            "decision_reason":           claim["decision_reason"],
            "member_message":            claim["member_message"],
            "network_discount_applied":  claim["network_discount_applied"],
            "copay_deducted":            claim["copay_deducted"],
            "manual_review_recommended": claim["manual_review_recommended"],
            "component_failures":        claim["component_failures"],
            "created_at":                claim["created_at"].isoformat()
                                         if hasattr(claim["created_at"], "isoformat")
                                         else str(claim["created_at"]),
        },
        "trace": trace,
    }


# ── GET all claims for a member ───────────────────────────────────────────────

@router.get("/member/{member_id}")
async def list_member_claims(
    member_id: str,
    limit: int = 20,
    conn: asyncpg.Connection = Depends(get_conn),
):
    rows = await get_member_claims(conn, member_id, limit=limit)
    return {
        "member_id": member_id,
        "claims": [
            {
                "claim_id":       r["claim_id"],
                "treatment_date": r["treatment_date"],
                "claim_category": r["claim_category"],
                "claimed_amount": r["claimed_amount"],
                "decision":       r["decision"],
                "approved_amount":r["approved_amount"],
                "created_at":     r["created_at"].isoformat()
                                  if hasattr(r["created_at"], "isoformat")
                                  else str(r["created_at"]),
            }
            for r in rows
        ],
    }