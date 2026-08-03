from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from app.config import default_runtime_paths
from app.database.schema import (
    MIGRATION_STATEMENTS,
    POST_MIGRATION_STATEMENTS,
    SCHEMA_STATEMENTS,
    SCHEMA_VERSION,
)

DEFAULT_DATABASE_NAME = "quant_app.sqlite3"


def default_database_path() -> Path:
    return default_runtime_paths().data_dir / DEFAULT_DATABASE_NAME


@contextmanager
def connect_database(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or default_database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5.0)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
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
        connection.execute(SCHEMA_STATEMENTS[0])
        row = connection.execute("SELECT MAX(version) AS version FROM schema_migrations").fetchone()
        current_version = row["version"] if row else None
        if current_version is not None and int(current_version) > SCHEMA_VERSION:
            raise RuntimeError(f"数据库版本 {current_version} 高于程序支持版本 {SCHEMA_VERSION}")

        for statement in SCHEMA_STATEMENTS[1:]:
            connection.execute(statement)
        if current_version is None:
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, datetime.now(UTC).isoformat()),
            )
        else:
            for version in range(int(current_version) + 1, SCHEMA_VERSION + 1):
                for statement in MIGRATION_STATEMENTS.get(version, []):
                    _execute_migration_statement(connection, statement)
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, datetime.now(UTC).isoformat()),
                )
        for statement in POST_MIGRATION_STATEMENTS:
            connection.execute(statement)
    return path


def _execute_migration_statement(
    connection: sqlite3.Connection,
    statement: str,
) -> None:
    normalized = " ".join(statement.split())
    parts = normalized.split()
    if len(parts) >= 6 and parts[0:2] == ["ALTER", "TABLE"]:
        table_name = parts[2]
        if parts[3:5] == ["ADD", "COLUMN"]:
            column_name = parts[5]
            columns = {
                str(row["name"])
                for row in connection.execute(
                    f"PRAGMA table_info({table_name})"
                ).fetchall()
            }
            if column_name in columns:
                return
    connection.execute(statement)


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
