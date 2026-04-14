"""
HTTP API for AgentWeave: agent registration, search, usage logging with idempotent
request IDs, and aggregated usage by target. Intended as a small, readable demo
for an internship assessment (see package docstring in ``app.__init__``).
"""

from __future__ import annotations

import json
import math
import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.database import get_db, init_db
from app.models import (
    AgentCreate,
    AgentOut,
    UsageCreate,
    UsageIgnored,
    UsageRecorded,
    UsageSummaryOut,
    UsageSummaryRow,
)
from app.utils import extract_keywords_from_description, merge_manual_and_extracted_tags

Db = Annotated[sqlite3.Connection, Depends(get_db)]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="AgentWeave", lifespan=lifespan)


def _success(data):
    return {"status": "success", "data": data}


@app.exception_handler(RequestValidationError)
async def request_validation_handler(_request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "status": "error",
            "error": {
                "code": "validation_error",
                "message": "Request body or query parameters failed validation.",
                "details": exc.errors(),
            },
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_request, exc: StarletteHTTPException):
    """Return application errors as a flat JSON object (no ``detail`` wrapper)."""
    error_payload: dict
    if isinstance(exc.detail, dict):
        error_payload = {
            "code": str(exc.detail.get("error", "http_error")),
            "message": str(exc.detail.get("message", "Request failed.")),
        }
        if "existing" in exc.detail:
            error_payload["existing"] = exc.detail["existing"]
        if "details" in exc.detail:
            error_payload["details"] = exc.detail["details"]
    else:
        error_payload = {
            "code": "http_error",
            "message": str(exc.detail),
        }
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "error": error_payload},
    )


def _agent_row_to_out(row: sqlite3.Row) -> AgentOut:
    raw = row["tags"] or "[]"
    try:
        parsed = json.loads(raw)
        tags = [str(x) for x in parsed] if isinstance(parsed, list) else []
    except json.JSONDecodeError:
        tags = []
    desc = str(row["description"])
    extracted = extract_keywords_from_description(desc)
    return AgentOut(
        id=int(row["id"]),
        name=row["name"],
        description=desc,
        endpoint=row["endpoint"],
        tags=tags,
        tags_from_description=extracted,
    )


def _resolve_agent_name(conn: sqlite3.Connection, name: str) -> str | None:
    row = conn.execute(
        "SELECT name FROM agents WHERE lower(name) = lower(?) LIMIT 1",
        (name,),
    ).fetchone()
    return str(row["name"]) if row else None


@app.post("/agents", status_code=status.HTTP_201_CREATED)
def create_agent(body: AgentCreate, conn: Db):
    extracted = extract_keywords_from_description(body.description)
    merged = merge_manual_and_extracted_tags(body.tags, extracted)
    tags_json = json.dumps(merged)
    try:
        cur = conn.execute(
            """
            INSERT INTO agents (name, description, endpoint, tags)
            VALUES (?, ?, ?, ?)
            """,
            (body.name, body.description, body.endpoint, tags_json),
        )
        conn.commit()
        new_id = int(cur.lastrowid)
    except sqlite3.IntegrityError as e:
        conn.rollback()
        if "agents.name" in str(e) or "UNIQUE constraint failed" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "agent_name_taken",
                    "message": f"An agent with name {body.name!r} already exists.",
                },
            ) from e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "database_error",
                "message": "Could not create agent due to a database constraint.",
            },
        ) from e
    except sqlite3.Error as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "database_error", "message": str(e)},
        ) from e

    row = conn.execute("SELECT * FROM agents WHERE id = ?", (new_id,)).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "database_error", "message": "Agent was created but could not be read back."},
        )
    return _success(_agent_row_to_out(row).model_dump())


@app.get("/agents")
def list_agents(conn: Db):
    try:
        rows = conn.execute(
            "SELECT * FROM agents ORDER BY id ASC",
        ).fetchall()
    except sqlite3.Error as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "database_error", "message": str(e)},
        ) from e
    return _success([_agent_row_to_out(r).model_dump() for r in rows])


@app.get("/search")
def search_agents(
    conn: Db,
    q: str = Query(..., min_length=1, description="Search text (name or description)"),
):
    term = q.strip()
    if not term:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "error": "invalid_query",
                "message": "Query parameter 'q' must contain non-whitespace characters.",
            },
        )
    try:
        rows = conn.execute(
            """
            SELECT * FROM agents
            WHERE lower(name) LIKE '%' || lower(?) || '%'
               OR lower(description) LIKE '%' || lower(?) || '%'
            ORDER BY id ASC
            """,
            (term, term),
        ).fetchall()
    except sqlite3.Error as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "database_error", "message": str(e)},
        ) from e
    return _success([_agent_row_to_out(r).model_dump() for r in rows])


@app.post(
    "/usage",
    status_code=status.HTTP_200_OK,
)
def log_usage(body: UsageCreate, conn: Db):
    caller_name = _resolve_agent_name(conn, body.caller)
    if caller_name is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "caller_not_found",
                "message": f"No agent exists with name matching caller {body.caller!r}.",
            },
        )

    target_name = _resolve_agent_name(conn, body.target)
    if target_name is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "target_not_found",
                "message": f"No agent exists with name matching target {body.target!r}.",
            },
        )

    try:
        cur = conn.execute(
            """
            INSERT INTO usage_events (caller, target, units, request_id)
            VALUES (?, ?, ?, ?)
            """,
            (caller_name, target_name, float(body.units), body.request_id),
        )
        conn.commit()
        new_id = int(cur.lastrowid)
    except sqlite3.IntegrityError as e:
        conn.rollback()
        row = conn.execute(
            "SELECT caller, target, units FROM usage_events WHERE request_id = ?",
            (body.request_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "database_error",
                    "message": "Could not resolve duplicate request_id after insert failure.",
                },
            ) from e

        same_caller = str(row["caller"]) == caller_name
        same_target = str(row["target"]) == target_name
        same_units = math.isclose(
            float(row["units"]),
            float(body.units),
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        if same_caller and same_target and same_units:
            return _success(
                UsageIgnored(
                request_id=body.request_id,
                message=(
                    "Duplicate request_id: usage was already recorded; "
                    "this request was ignored and did not increase totals."
                ),
                ).model_dump()
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "request_id_reuse",
                "message": (
                    "request_id is already used for a different usage record; "
                    "refusing to overwrite."
                ),
                "existing": {
                    "caller": str(row["caller"]),
                    "target": str(row["target"]),
                    "units": float(row["units"]),
                },
            },
        ) from e
    except sqlite3.Error as e:
        conn.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "database_error", "message": str(e)},
        ) from e

    row = conn.execute(
        "SELECT caller, target, units FROM usage_events WHERE id = ?",
        (new_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "database_error", "message": "Usage was logged but could not be read back."},
        )

    return _success(
        UsageRecorded(
            request_id=body.request_id,
            caller=str(row["caller"]),
            target=str(row["target"]),
            units=float(row["units"]),
        ).model_dump()
    )


@app.get("/usage-summary")
def usage_summary(conn: Db):
    try:
        rows = conn.execute(
            """
            SELECT target, SUM(units) AS total_units
            FROM usage_events
            GROUP BY target
            ORDER BY total_units DESC, target ASC
            """,
        ).fetchall()
    except sqlite3.Error as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "database_error", "message": str(e)},
        ) from e

    out_rows = [
        UsageSummaryRow(target=str(r["target"]), total_units=float(r["total_units"]))
        for r in rows
    ]
    return _success(UsageSummaryOut(by_target=out_rows).model_dump())
