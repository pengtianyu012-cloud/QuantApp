from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from app.config import default_runtime_paths
from app.database.schema import SCHEMA_STATEMENTS, SCHEMA_VERSION

DEFAULT_DATABASE_NAME = "quant_app.sqlite3"


def default_database_path() -> Path:
    return default_runtime_paths().data_dir / DEFAULT_DATABASE_NAME


@contextmanager
def connect_database(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or default_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(db_path: Path | None = None) -> Path:
    path = db_path or default_database_path()
    with connect_database(path) as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (SCHEMA_VERSION, datetime.now(UTC).isoformat()),
        )
    return path


def get_schema_version(db_path: Path | None = None) -> int | None:
    path = db_path or default_database_path()
    if not path.exists():
        return None
    with connect_database(path) as connection:
        row = connection.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
    return int(row["version"]) if row and row["version"] is not None else None


def list_tables(db_path: Path | None = None) -> set[str]:
    path = db_path or default_database_path()
    with connect_database(path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    return {str(row["name"]) for row in rows}
