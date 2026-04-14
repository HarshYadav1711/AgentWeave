# AgentWeave

Local-only FastAPI service that registers **agents** (name, description, endpoint, tags) and records **usage** between them with **idempotent** `request_id` handling. Persistence is **SQLite** via the standard library (`sqlite3`); there is **no ORM** and no external database.

## Problem understanding

The core job is to **register agents**, let clients **search** them, **log usage** from a caller to a target with a **stable request id**, and **aggregate** usage per target—without ever **double-counting** when a client retries the same `request_id`. The API should **validate inputs**, return **predictable JSON**, and stay **small enough to review** in an interview setting.

## How to run locally

Python **3.10+** recommended.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

- API base: `http://127.0.0.1:8000`
- OpenAPI UI: `http://127.0.0.1:8000/docs`
- SQLite file (created on startup): `agentweave.db` in the project root

## Testing (optional, local)

**Automated (pytest):** installs dev deps and runs a small demo suite (isolated temp DB per run).

```bash
pip install -r requirements-dev.txt
pytest
```

**Manual (curl):** step-by-step copy-paste flow — see [`MANUAL_TESTS.md`](MANUAL_TESTS.md).

## Example requests

Examples use `curl` against the default port; adjust the URL if needed.

**Create an agent** (manual tags are merged with keywords extracted from `description`):

```bash
curl -s -X POST "http://127.0.0.1:8000/agents" -H "Content-Type: application/json" \
  -d '{"name":"Router","description":"Routes traffic for NLP workloads","endpoint":"http://localhost:9000","tags":["prod"]}'
```

**List agents**

```bash
curl -s "http://127.0.0.1:8000/agents"
```

**Search (case-insensitive name or description)**

```bash
curl -s "http://127.0.0.1:8000/search?q=nlp"
```

**Log usage** (caller/target must match an existing agent name, case-insensitive)

```bash
curl -s -X POST "http://127.0.0.1:8000/usage" -H "Content-Type: application/json" \
  -d '{"caller":"Router","target":"Router","units":2.5,"request_id":"req-2026-04-14-001"}'
```

**Retry the same `request_id`** (same payload → same `request_id` is **ignored**, no double-counting)

```bash
curl -s -X POST "http://127.0.0.1:8000/usage" -H "Content-Type: application/json" \
  -d '{"caller":"Router","target":"Router","units":2.5,"request_id":"req-2026-04-14-001"}'
```

**Usage summary** (highest `total_units` first)

```bash
curl -s "http://127.0.0.1:8000/usage-summary"
```

## API overview

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/agents` | Create agent (`name`, `description`, `endpoint`, optional `tags`) |
| `GET` | `/agents` | List all agents |
| `GET` | `/search` | `q` query; case-insensitive match on **name** or **description** |
| `POST` | `/usage` | Log usage; idempotent on `request_id` |
| `GET` | `/usage-summary` | `total_units` per `target`, **descending by usage** (ties tie-break by `target`) |

**Responses**

- Success envelope:
  - `{ "status": "success", "data": ... }`
- Error envelope:
  - `{ "status": "error", "error": { "code": "...", "message": "...", ... } }`
- **`POST /usage`** keeps idempotency explicit: duplicate `request_id` with the same payload returns success with `data.status: "ignored"` and `data.operation: "ignored_duplicate_request"` (totals do not increase).

**Tags**

- Manual tags from the client are merged with **deterministic keyword extraction** from `description` (alphanumeric tokens, length ≥ 3, small fixed stopword list, first-seen order, capped). See `app/utils.py`.

## Layout

| Path | Role |
|------|------|
| `app/main.py` | Routes, error shaping, startup |
| `app/database.py` | `sqlite3` + `init_db()` |
| `app/models.py` | Pydantic request/response models |
| `app/utils.py` | Keyword extraction + tag merge |
| `tests/test_demo.py` | Pytest demo cases (temp DB) |
| `MANUAL_TESTS.md` | Copy-paste curl walkthrough |

## Design answers

### 1) Billing without double charging

Treat each **`request_id` as an idempotency key** at the **database** layer: a **unique constraint** on `usage_events.request_id` guarantees at most one row per key. When a client retries with the same `request_id` and the same logical usage, the insert **fails once**, the handler **detects the duplicate**, and returns an **explicit ignored response** without inserting a second row—so **aggregates and totals never increase twice**. If the same `request_id` is reused with a **different** payload, the API returns **409** so ambiguous retries cannot silently corrupt billing.

### 2) Scaling to 100K agents

**100K agent rows** is still modest for SQLite with a **single writer**; the main levers are **indexes** and **read patterns**. I would add a **case-insensitive index** on `lower(name)` (or a `name_normalized` column) to speed lookups used by `/usage` resolution, keep **search** bounded (pagination or `LIMIT` if the product grows), and move to a **client/server database** (e.g. PostgreSQL) if **concurrent writes** or **multi-instance** deployment is required. The **API shape** (parameterized SQL, Pydantic validation, idempotent usage) stays the same; only the **connection and migration** story changes.

## AI reflection

I used an AI assistant to **accelerate** implementation and to **pressure-check** edge cases (idempotency conflicts, float rounding, response consistency). I **reviewed** every path and kept the design **small** on purpose: **stdlib SQLite**, **no ORM**, **no extra services**, and **deterministic** tag extraction so the project is **easy to explain live**. The final choices are mine: **flat error JSON**, **explicit ignored operation** for duplicate `request_id`, and **summary sorted by highest usage** to make demos readable.
