from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class ClaimRecord(Base):
    __tablename__ = "claims"

    claim_id    = Column(String, primary_key=True)
    member_id   = Column(String, nullable=False, index=True)
    policy_id   = Column(String, nullable=False)
    claim_category = Column(String, nullable=False)
    treatment_date = Column(String, nullable=False)
    claimed_amount = Column(Float, nullable=False)
    hospital_name  = Column(String, nullable=True)

    decision    = Column(String, nullable=True)
    approved_amount = Column(Float, default=0.0)
    confidence_score = Column(Float, default=0.0)
    rejection_reasons = Column(JSON, default=list)
    decision_reason = Column(Text, default="")
    member_message  = Column(Text, default="")

    network_discount_applied = Column(Float, default=0.0)
    copay_deducted           = Column(Float, default=0.0)
    manual_review_recommended = Column(String, default="false")
    component_failures        = Column(JSON, default=list)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DocumentRecord(Base):
    __tablename__ = "claim_documents"

    id          = Column(String, primary_key=True)
    claim_id    = Column(String, ForeignKey("claims.claim_id"), nullable=False, index=True)
    file_name   = Column(String, nullable=False)
    classified_type = Column(String, nullable=True)
    quality     = Column(String, nullable=True)
    extracted_data  = Column(JSON, default=dict)
    overall_confidence = Column(Float, default=0.0)
    created_at  = Column(DateTime, default=datetime.utcnow)


class ClaimTraceRecord(Base):
    __tablename__ = "claim_traces"

    claim_id   = Column(String, ForeignKey("claims.claim_id"), primary_key=True)
    trace_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)