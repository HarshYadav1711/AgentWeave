# AgentWeave

Minimal FastAPI scaffold using **Pydantic**, **sqlite3** (stdlib), and **Uvicorn**. No ORM, no external database.

## Setup

Python 3.10+ recommended.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

## Run

From the repository root:

```bash
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API.

The SQLite file `agentweave.db` is created on startup next to the project root.

## Layout

| Path | Role |
|------|------|
| `app/main.py` | FastAPI app; calls `init_db()` on startup |
| `app/database.py` | `sqlite3` connection + `init_db()` |
| `app/models.py` | Pydantic models for `agents` / `usage_events` |
| `app/utils.py` | Placeholder for shared helpers |

## Schema

**agents:** `id`, `name` (UNIQUE), `description`, `endpoint`, `tags` (JSON text)

**usage_events:** `id`, `caller`, `target`, `units`, `request_id` (UNIQUE), `created_at` (default `datetime('now')`)

## API

| Method | Path | Notes |
|--------|------|--------|
| `POST` | `/agents` | Create agent; validates `name`, `description`, `endpoint` (and optional `tags`) |
| `GET` | `/agents` | List all agents |
| `GET` | `/search` | `q` query; case-insensitive match on **name** or **description** |
| `POST` | `/usage` | Log usage; `caller` / `target` must match existing agent names (case-insensitive); idempotent on `request_id` |
| `GET` | `/usage-summary` | `total_units` per `target`, sorted by `target` |

Duplicate `request_id` with the same payload returns `status: "ignored"` and does not double-count. Conflicting reuse of `request_id` returns `409`.
