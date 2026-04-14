from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Unit(str, Enum):
    TOKENS = "tokens"
    SECONDS = "seconds"
    REQUESTS = "requests"


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=10_000)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, v: list[str]) -> list[str]:
        """Bonus: strip, lowercase, dedupe, preserve first-seen order, cap count."""
        seen: set[str] = set()
        out: list[str] = []
        for raw in v:
            t = raw.strip().lower()
            if not t:
                continue
            if len(t) > 64:
                raise ValueError("each tag must be at most 64 characters")
            if t in seen:
                continue
            seen.add(t)
            out.append(t)
            if len(out) > 32:
                raise ValueError("at most 32 tags allowed")
        return out


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    tags: list[str]


class InvocationCreate(BaseModel):
    request_id: str = Field(..., min_length=1, max_length=128)
    agent_id: int = Field(..., ge=1)
    unit: Unit
    amount: float = Field(..., gt=0)


class InvocationOut(BaseModel):
    request_id: str
    agent_id: int
    unit: Unit
    amount: float
    idempotent_replay: bool = False
