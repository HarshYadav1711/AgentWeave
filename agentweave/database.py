from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Generator

_DB_PATH = Path(__file__).resolve().parent.parent / "agentweave.db"


def get_db_path() -> Path:
    return _DB_PATH


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS agents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            tags_json TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS invocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT NOT NULL UNIQUE,
            agent_id INTEGER NOT NULL REFERENCES agents(id) ON DELETE RESTRICT,
            unit TEXT NOT NULL,
            amount REAL NOT NULL,
            CHECK (amount > 0)
        );
        """
    )
    conn.commit()


def db_session() -> Generator[sqlite3.Connection, None, None]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
