from __future__ import annotations
import os
import sqlite3
from pathlib import Path

def get_db_path() -> str:
    data_dir = os.getenv("APP_DATA_DIR", "/data")
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    return str(Path(data_dir) / "app.db")

def init_db() -> None:
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS uploads (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            stored_path TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS envs (
            name TEXT PRIMARY KEY,
            payload_encrypted BLOB NOT NULL,
            platform TEXT NOT NULL,
            org_id TEXT,
            created_at TEXT NOT NULL
        )
        """)

        # Safe migration for existing DB
        try:
            cur.execute("ALTER TABLE envs ADD COLUMN platform TEXT")
        except Exception:
            pass

        try:
            cur.execute("ALTER TABLE envs ADD COLUMN org_id TEXT")
        except Exception:
            pass

        cur.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            id TEXT PRIMARY KEY,
            upload_id TEXT NOT NULL,
            env_name TEXT NOT NULL,
            plan_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        conn.commit()
    finally:
        conn.close()

def db_connect() -> sqlite3.Connection:
    return sqlite3.connect(get_db_path())