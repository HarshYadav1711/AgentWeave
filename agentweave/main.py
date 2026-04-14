from __future__ import annotations

import json
import math
import sqlite3
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from agentweave.database import connect, db_session, init_db
from agentweave.schemas import AgentCreate, AgentOut, InvocationCreate, InvocationOut, Unit

# --- App & DB lifecycle ------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = connect()
    try:
        init_db(conn)
    finally:
        conn.close()
    yield


app = FastAPI(title="AgentWeave", version="0.1.0", lifespan=lifespan)

DbConn = Annotated[sqlite3.Connection, Depends(db_session)]


# --- Helpers -----------------------------------------------------------------


def _row_agent(row: sqlite3.Row) -> AgentOut:
    tags = json.loads(row["tags_json"] or "[]")
    return AgentOut(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        tags=tags,
    )


def _row_invocation(row: sqlite3.Row, *, idempotent_replay: bool) -> InvocationOut:
    return InvocationOut(
        request_id=row["request_id"],
        agent_id=row["agent_id"],
        unit=Unit(row["unit"]),
        amount=float(row["amount"]),
        idempotent_replay=idempotent_replay,
    )


# --- Routes ------------------------------------------------------------------


@app.post("/agents", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
def create_agent(body: AgentCreate, conn: DbConn):
    tags_json = json.dumps(body.tags)
    try:
        cur = conn.execute(
            "INSERT INTO agents (name, description, tags_json) VALUES (?, ?, ?)",
            (body.name, body.description, tags_json),
        )
        conn.commit()
        new_id = int(cur.lastrowid)
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
            detail={"error": "database_error", "message": "failed to read new agent"},
        )
    return _row_agent(row)


@app.get("/agents", response_model=list[AgentOut])
def list_agents(
    conn: DbConn,
    q: str | None = Query(
        default=None,
        description="Case-insensitive search across name and description",
    ),
):
    if q is None or not q.strip():
        rows = conn.execute(
            "SELECT * FROM agents ORDER BY id ASC",
        ).fetchall()
    else:
        term = q.strip()
        rows = conn.execute(
            """
            SELECT * FROM agents
            WHERE lower(name) LIKE '%' || lower(?) || '%'
               OR lower(description) LIKE '%' || lower(?) || '%'
            ORDER BY id ASC
            """,
            (term, term),
        ).fetchall()
    return [_row_agent(r) for r in rows]


@app.post("/invocations", response_model=InvocationOut)
def create_invocation(body: InvocationCreate, conn: DbConn):
    agent = conn.execute(
        "SELECT id FROM agents WHERE id = ?",
        (body.agent_id,),
    ).fetchone()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "unknown_agent",
                "message": f"no agent with id {body.agent_id}",
            },
        )

    unit_value = body.unit.value
    try:
        cur = conn.execute(
            """
            INSERT INTO invocations (request_id, agent_id, unit, amount)
            VALUES (?, ?, ?, ?)
            """,
            (body.request_id, body.agent_id, unit_value, body.amount),
        )
        conn.commit()
        new_id = int(cur.lastrowid)
    except sqlite3.IntegrityError:
        conn.rollback()
        row = conn.execute(
            "SELECT * FROM invocations WHERE request_id = ?",
            (body.request_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "idempotency_conflict",
                    "message": "request_id collides with a different stored invocation",
                },
            )
        if (
            int(row["agent_id"]) != body.agent_id
            or row["unit"] != unit_value
            or not math.isclose(float(row["amount"]), float(body.amount), rel_tol=0.0, abs_tol=1e-9)
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "idempotency_mismatch",
                    "message": "same request_id must repeat the same agent_id, unit, and amount",
                },
            )
        return _row_invocation(row, idempotent_replay=True)

    row = conn.execute("SELECT * FROM invocations WHERE id = ?", (new_id,)).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "database_error", "message": "failed to read new invocation"},
        )
    return _row_invocation(row, idempotent_replay=False)


# --- Consistent validation errors --------------------------------------------


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "message": "request validation failed",
            "details": exc.errors(),
        },
    )
