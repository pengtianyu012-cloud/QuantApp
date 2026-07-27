import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.database import (
    CORE_TABLES,
    SCHEMA_VERSION,
    get_schema_version,
    initialize_database,
    list_tables,
)
from app.database.connection import connect_database


class DatabaseTests(unittest.TestCase):
    def test_initialize_database_creates_core_tables(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.sqlite3"

            initialize_database(db_path)

            tables = list_tables(db_path)
            self.assertTrue(set(CORE_TABLES).issubset(tables))
            self.assertIn("schema_migrations", tables)
            self.assertEqual(get_schema_version(db_path), SCHEMA_VERSION)

    def test_schema_version_is_none_before_initialization(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "missing.sqlite3"

            self.assertIsNone(get_schema_version(db_path))

    def test_version_one_database_migrates_position_recovery_columns(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "legacy.sqlite3"
            connection = sqlite3.connect(db_path)
            connection.execute(
                "CREATE TABLE schema_migrations "
                "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) "
                "VALUES (1, '2026-07-27T00:00:00+00:00')"
            )
            connection.execute(
                """
                CREATE TABLE positions (
                    account_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    available_quantity INTEGER NOT NULL,
                    cost_price TEXT NOT NULL,
                    market_value TEXT NOT NULL,
                    last_price TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (account_id, symbol)
                )
                """
            )
            connection.commit()
            connection.close()

            initialize_database(db_path)

            with connect_database(db_path) as migrated:
                columns = {
                    str(row["name"])
                    for row in migrated.execute("PRAGMA table_info(positions)").fetchall()
                }
            self.assertEqual(get_schema_version(db_path), SCHEMA_VERSION)
            self.assertIn("name", columns)
            self.assertIn("last_buy_date", columns)


if __name__ == "__main__":
    unittest.main()
