"""Pydantic models for requests and responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=10_000)
    endpoint: str = Field(..., min_length=1, max_length=2_048)
    tags: list[str] = Field(default_factory=list)

    @field_validator("name", "description", "endpoint", mode="before")
    @classmethod
    def strip_agent_strings(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("name", "endpoint")
    @classmethod
    def name_endpoint_nonempty(cls, v: str) -> str:
        if not v:
            raise ValueError("must not be empty")
        return v

    @field_validator("tags")
    @classmethod
    def tag_strings(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for t in v:
            if not isinstance(t, str):
                raise TypeError("each tag must be a string")
            s = t.strip()
            if s:
                out.append(s)
        return out


class AgentOut(BaseModel):
    ok: Literal[True] = True
    id: int
    name: str
    description: str
    endpoint: str
    tags: list[str]
    tags_from_description: list[str] = Field(
        default_factory=list,
        description="Keywords extracted deterministically from description (same rules as stored merge).",
    )


class UsageCreate(BaseModel):
    caller: str = Field(..., min_length=1, max_length=200)
    target: str = Field(..., min_length=1, max_length=200)
    units: float = Field(..., gt=0)
    request_id: str = Field(..., min_length=1, max_length=128)

    @field_validator("caller", "target", "request_id", mode="before")
    @classmethod
    def strip_usage_strings(cls, v: object) -> object:
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("caller", "target", "request_id")
    @classmethod
    def not_empty_usage(cls, v: str) -> str:
        if not v:
            raise ValueError("must not be empty")
        return v


class UsageRecorded(BaseModel):
    ok: Literal[True] = True
    status: Literal["recorded"] = "recorded"
    operation: Literal["record_usage"] = "record_usage"
    request_id: str
    caller: str
    target: str
    units: float


class UsageIgnored(BaseModel):
    ok: Literal[True] = True
    status: Literal["ignored"] = "ignored"
    operation: Literal["ignored_duplicate_request"] = "ignored_duplicate_request"
    ignored_duplicate_request: Literal[True] = True
    request_id: str
    reason: Literal["duplicate_request_id"] = "duplicate_request_id"
    message: str = (
        "This request_id was already logged; usage was not counted again."
    )


class UsageSummaryRow(BaseModel):
    target: str
    total_units: float


class UsageSummaryOut(BaseModel):
    ok: Literal[True] = True
    by_target: list[UsageSummaryRow]
