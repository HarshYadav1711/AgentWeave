"""Pytest fixtures: isolated SQLite file per test session."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Point the app at a temporary DB and return a TestClient."""
    db_file = tmp_path / "agentweave_test.db"
    monkeypatch.setattr("app.database._DB_PATH", db_file)

    from app.database import init_db

    init_db()

    from app.main import app

    return TestClient(app)
