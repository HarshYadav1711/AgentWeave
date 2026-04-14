"""
AgentWeave — internship assessment API (local-only).

Registers lightweight "agents" (name, description, endpoint) and records
usage between them with idempotent ``request_id`` handling backed by SQLite.
This package holds the FastAPI app (``app.main``), persistence (``app.database``),
Pydantic models (``app.models``), and small deterministic helpers (``app.utils``).
"""
