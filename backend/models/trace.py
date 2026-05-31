from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TraceEntry(BaseModel):
    component: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: int = 0
    input_summary: dict[str, Any] = {}
    output_summary: dict[str, Any] = {}
    error: str | None = None


class ClaimTrace(BaseModel):
    claim_id: UUID | None = None
    entries: list[TraceEntry] = []
    total_duration_ms: int = 0

    def add(self, entry: TraceEntry) -> None:
        self.entries.append(entry)
        self.total_duration_ms += entry.duration_ms