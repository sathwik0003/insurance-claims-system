"""
Database connection pool using raw asyncpg.

We use a pool (not one connection per request) so rapid back-to-back
requests (e.g. running all 12 eval cases) don't exhaust Supabase's
connection limit or time out on authentication.

statement_cache_size=0 disables prepared statements, which are
incompatible with Supabase's pgbouncer transaction pooler.
"""

import json
import os

import asyncpg

from config import get_settings

_s = get_settings()
_pool: asyncpg.Pool | None = None


def _pg_url() -> str:
    url = _s.database_url
    for prefix in ["postgresql+asyncpg://", "postgresql+psycopg2://"]:
        if url.startswith(prefix):
            return "postgresql://" + url[len(prefix):]
    return url


def _json_encoder(val):
    return json.dumps(val)


def _json_decoder(val):
    return json.loads(val)


async def init_pool() -> None:
    """Call once at app startup (from lifespan)."""
    global _pool

    async def _setup(conn):
        """Run after each connection is created — register JSON codecs."""
        await conn.set_type_codec(
            "jsonb", encoder=_json_encoder, decoder=_json_decoder,
            schema="pg_catalog"
        )
        await conn.set_type_codec(
            "json", encoder=_json_encoder, decoder=_json_decoder,
            schema="pg_catalog"
        )

    _pool = await asyncpg.create_pool(
        _pg_url(),
        min_size=1,
        max_size=5,           # stay well within Supabase free-tier limits
        statement_cache_size=0,
        init=_setup,
        command_timeout=30,
    )


async def close_pool() -> None:
    """Call at app shutdown (from lifespan)."""
    global _pool
    if _pool:
        import asyncio
        try:
            # Give it 3 seconds — on hot-reload the event loop closes
            # before pool connections can cleanly handshake goodbye with Supabase.
            await asyncio.wait_for(_pool.close(), timeout=3.0)
        except (asyncio.TimeoutError, Exception):
            # Terminate forcefully — acceptable on shutdown/reload
            try:
                _pool.terminate()
            except Exception:
                pass
        _pool = None


async def get_conn():
    """
    FastAPI dependency — acquires a connection from the pool,
    yields it to the route handler, then releases it back.
    """
    if _pool is None:
        raise RuntimeError("Database pool not initialised — did lifespan run?")
    async with _pool.acquire() as conn:
        yield conn