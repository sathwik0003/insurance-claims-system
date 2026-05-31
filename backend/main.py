import logging
from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from db.session import close_pool, init_pool
from routers.claims import router as claims_router
from routers.members import router as members_router

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def _pg_url() -> str:
    url = settings.database_url
    for prefix in ["postgresql+asyncpg://", "postgresql+psycopg2://"]:
        if url.startswith(prefix):
            return "postgresql://" + url[len(prefix):]
    return url


_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS claims (
    claim_id VARCHAR PRIMARY KEY,
    member_id VARCHAR NOT NULL,
    policy_id VARCHAR NOT NULL,
    claim_category VARCHAR NOT NULL,
    treatment_date VARCHAR NOT NULL,
    claimed_amount FLOAT NOT NULL,
    hospital_name VARCHAR,
    decision VARCHAR,
    approved_amount FLOAT DEFAULT 0.0,
    confidence_score FLOAT DEFAULT 0.0,
    rejection_reasons JSONB DEFAULT '[]',
    decision_reason TEXT DEFAULT '',
    member_message TEXT DEFAULT '',
    network_discount_applied FLOAT DEFAULT 0.0,
    copay_deducted FLOAT DEFAULT 0.0,
    manual_review_recommended VARCHAR DEFAULT 'false',
    component_failures JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_claims_member ON claims(member_id);

CREATE TABLE IF NOT EXISTS claim_documents (
    id VARCHAR PRIMARY KEY,
    claim_id VARCHAR NOT NULL REFERENCES claims(claim_id),
    file_name VARCHAR NOT NULL,
    classified_type VARCHAR,
    quality VARCHAR,
    extracted_data JSONB DEFAULT '{}',
    overall_confidence FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_docs_claim ON claim_documents(claim_id);

CREATE TABLE IF NOT EXISTS claim_traces (
    claim_id VARCHAR PRIMARY KEY REFERENCES claims(claim_id),
    trace_json JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Create tables (raw asyncpg — bypasses SQLAlchemy prepared stmts) ──
    conn = await asyncpg.connect(_pg_url(), statement_cache_size=0)
    try:
        await conn.execute(_CREATE_SQL)
        logger.info("PostgreSQL tables ready")
    finally:
        await conn.close()

    # ── Start connection pool for request handling ─────────────────────────
    await init_pool()
    logger.info("Connection pool ready (min=1, max=5)")

    yield

    # ── Shutdown ───────────────────────────────────────────────────────────
    await close_pool()
    logger.info("Connection pool closed")


app = FastAPI(
    title="Plum Claims Processing API",
    description="Multi-agent health insurance claims pipeline",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(claims_router)
app.include_router(members_router)


@app.get("/health", tags=["infra"])
async def health():
    return {"status": "ok", "env": settings.app_env}