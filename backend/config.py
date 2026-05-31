from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Groq ────────────────────────────────────────────────────────────
    groq_api_key: str
    groq_vision_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    groq_text_model: str = "llama-3.3-70b-versatile"

    # ── Database ─────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./claims.db"

    # ── Supabase storage ─────────────────────────────────────────────────
    supabase_s3_endpoint: str = ""
    supabase_s3_access_key: str = ""
    supabase_s3_secret_key: str = ""
    supabase_s3_region: str = "ap-northeast-1"
    supabase_storage_bucket: str = "claim-documents"

    # ── App ───────────────────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"

    # ── Paths ─────────────────────────────────────────────────────────────
    policy_data_path: Path = Path(__file__).parent / "data" / "policy_terms.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def async_database_url(self) -> str:
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.database_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()