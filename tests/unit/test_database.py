import sqlite3
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import APP_TIME_ZONE
from app.database import (
    CORE_TABLES,
    SCHEMA_VERSION,
    get_schema_version,
    initialize_database,
    list_tables,
)
from app.database.connection import connect_database
from app.models import OrderSide, OrderStatus, OrderType


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
                "VALUES (1, '2030-08-06T00:00:00+00:00')"
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

    def test_version_two_database_migrates_execution_and_snapshot_history(self) -> None:
        with TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "legacy-v2.sqlite3"
            connection = sqlite3.connect(db_path)
            connection.executescript(
                """
                CREATE TABLE schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
                CREATE TABLE accounts (
                    account_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    initial_cash TEXT NOT NULL,
                    cash TEXT NOT NULL,
                    total_assets TEXT NOT NULL,
                    max_drawdown TEXT NOT NULL DEFAULT '0',
                    risk_status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE orders (
                    order_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    limit_price TEXT,
                    status TEXT NOT NULL,
                    reason TEXT,
                    submitted_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE fills (
                    fill_id TEXT PRIMARY KEY,
                    order_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price TEXT NOT NULL,
                    commission TEXT NOT NULL,
                    tax TEXT NOT NULL,
                    transfer_fee TEXT NOT NULL,
                    slippage TEXT NOT NULL,
                    degraded_model INTEGER NOT NULL DEFAULT 0,
                    filled_at TEXT NOT NULL
                );
                CREATE TABLE portfolio_snapshots (
                    account_id TEXT NOT NULL,
                    snapshot_time TEXT NOT NULL,
                    cash TEXT NOT NULL,
                    market_value TEXT NOT NULL,
                    total_assets TEXT NOT NULL,
                    daily_pnl TEXT NOT NULL,
                    cumulative_return TEXT NOT NULL,
                    max_drawdown TEXT NOT NULL,
                    PRIMARY KEY (account_id, snapshot_time)
                );
                """
            )
            timestamp = datetime(
                2030,
                8,
                6,
                9,
                30,
                tzinfo=APP_TIME_ZONE,
            ).isoformat()
            connection.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (2, ?)",
                (timestamp,),
            )
            connection.execute(
                "INSERT INTO accounts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "SIM-001",
                    "legacy",
                    "100000",
                    "99500",
                    "99900",
                    "0.01",
                    "允许交易",
                    timestamp,
                    timestamp,
                ),
            )
            connection.execute(
                "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "O-LEGACY",
                    "SIM-001",
                    "000001.SZ",
                    OrderSide.BUY.value,
                    OrderType.NEXT_OPEN.value,
                    100,
                    None,
                    OrderStatus.PENDING_FILL.value,
                    "",
                    timestamp,
                    timestamp,
                ),
            )
            connection.execute(
                "INSERT INTO fills VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "F-LEGACY",
                    "O-LEGACY",
                    "000001.SZ",
                    OrderSide.BUY.value,
                    40,
                    "10",
                    "5",
                    "0",
                    "0.01",
                    "0.20",
                    0,
                    timestamp,
                ),
            )
            for hour, total_assets in ((10, "99900"), (15, "99800")):
                snapshot_time = datetime(
                    2030,
                    8,
                    6,
                    hour,
                    0,
                    tzinfo=APP_TIME_ZONE,
                ).isoformat()
                connection.execute(
                    "INSERT INTO portfolio_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        "SIM-001",
                        snapshot_time,
                        "99500",
                        "300",
                        total_assets,
                        "-100",
                        "-0.001",
                        "0.01",
                    ),
                )
            connection.commit()
            connection.close()

            initialize_database(db_path)

            with connect_database(db_path) as migrated:
                order = migrated.execute(
                    "SELECT * FROM orders WHERE order_id = 'O-LEGACY'"
                ).fetchone()
                account = migrated.execute(
                    "SELECT * FROM accounts WHERE account_id = 'SIM-001'"
                ).fetchone()
                event_count = migrated.execute(
                    "SELECT COUNT(*) FROM order_events WHERE order_id = 'O-LEGACY'"
                ).fetchone()[0]
                snapshot_count = migrated.execute(
                    "SELECT COUNT(*) FROM portfolio_snapshots "
                    "WHERE account_id = 'SIM-001'"
                ).fetchone()[0]

            assert order is not None
            assert account is not None
            self.assertEqual(get_schema_version(db_path), SCHEMA_VERSION)
            self.assertEqual(order["status"], OrderStatus.ELIGIBLE.value)
            self.assertEqual(order["filled_quantity"], 40)
            self.assertEqual(order["remaining_quantity"], 60)
            self.assertEqual(account["peak_total_assets"], "100000")
            self.assertEqual(event_count, 1)
            self.assertEqual(snapshot_count, 1)


if __name__ == "__main__":
    unittest.main()
