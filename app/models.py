"""Pydantic models aligned with database tables."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Agent(BaseModel):
    id: int | None = None
    name: str
    description: str = ""
    endpoint: str
    tags: list[str] = Field(default_factory=list)


class UsageEvent(BaseModel):
    id: int | None = None
    caller: str
    target: str
    units: float
    request_id: str
    created_at: str | None = None
