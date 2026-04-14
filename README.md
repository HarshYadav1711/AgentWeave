# AgentWeave

Small **local-only** FastAPI service for registering agents and recording idempotent usage invocations, backed by SQLite.

## Run

Requires **Python 3.10+**.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn agentweave.main:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for interactive OpenAPI.

The SQLite file is created next to the package as `agentweave.db` on first request.

## API (required + bonus)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/agents` | Create agent (`name`, `description`, optional `tags`) |
| `GET` | `/agents` | List agents; optional `q` searches **name and description** (case-insensitive) |
| `POST` | `/invocations` | Record usage (`request_id`, `agent_id`, `unit`, `amount`); **idempotent** on `request_id` |

**Units** (invalid values → `422`): `tokens`, `seconds`, `requests`.

**Bonus — tags:** trimmed, lowercased, deduplicated (first-seen order), max **32** tags, max **64** chars per tag.

**Idempotency:** `request_id` is **UNIQUE** in SQLite. Repeating the same `request_id` with the same `agent_id`, `unit`, and `amount` returns the stored row and `idempotent_replay: true`. The same `request_id` with different payload fields returns **409** with `idempotency_mismatch`.

**Validation:** `422` for missing/invalid bodies (Pydantic); `404` for unknown `agent_id`; consistent JSON error bodies for `HTTPException` cases above.

## Design notes

- **SQLite + `sqlite3`:** Fits a single-machine assessment with no extra services; foreign keys and a unique index on `request_id` give cheap correctness and idempotency without application-level locks.
- **Search:** `lower(name)` / `lower(description)` with `LIKE '%' || lower(?) || '%'` keeps case-insensitive matching in the database and avoids loading full tables for simple filters.
- **Responses:** Pydantic models for success payloads; `422` errors use a shared envelope via `RequestValidationError` handler so validation stays readable in clients.

## AI reflection

I used the model to **structure** the assignment (routes, schema, constraints) and to **cross-check** edge cases (idempotent replay vs conflicting reuse of `request_id`). Final tradeoffs—SQLite, minimal endpoints, and explicit mismatch errors—were chosen to stay **small, reviewable, and faithful to the brief** rather than to add frameworks or features. Any production extension would start with tests, migrations, and a migration path off a single-file DB—not extra abstractions in this repo.
