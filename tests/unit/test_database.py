import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from app.database import CORE_TABLES, SCHEMA_VERSION, get_schema_version, initialize_database, list_tables


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


if __name__ == "__main__":
    unittest.main()
