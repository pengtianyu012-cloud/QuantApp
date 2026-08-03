from __future__ import annotations

SCHEMA_VERSION = 4

CORE_TABLES = [
    "instruments",
    "trading_calendar",
    "daily_bars",
    "intraday_bars",
    "latest_quotes",
    "order_books",
    "strategies",
    "strategy_runs",
    "signals",
    "accounts",
    "positions",
    "orders",
    "order_events",
    "fills",
    "portfolio_snapshots",
    "risk_events",
    "backtest_runs",
    "backtest_metrics",
    "app_settings",
    "data_quality_reports",
]

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS instruments (
        symbol TEXT PRIMARY KEY,
        code TEXT NOT NULL,
        exchange TEXT NOT NULL,
        name TEXT NOT NULL,
        board TEXT NOT NULL,
        industry TEXT,
        listed_date TEXT NOT NULL,
        is_st INTEGER NOT NULL DEFAULT 0,
        is_delisting INTEGER NOT NULL DEFAULT 0,
        is_delisted INTEGER NOT NULL DEFAULT 0,
        is_suspended INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS trading_calendar (
        trade_date TEXT PRIMARY KEY,
        exchange TEXT NOT NULL,
        is_open INTEGER NOT NULL,
        market_phase TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS daily_bars (
        symbol TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        open_price TEXT NOT NULL,
        high_price TEXT NOT NULL,
        low_price TEXT NOT NULL,
        close_price TEXT NOT NULL,
        volume INTEGER NOT NULL,
        amount TEXT NOT NULL,
        adjusted_flag TEXT NOT NULL DEFAULT 'none',
        source TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (symbol, trade_date, adjusted_flag)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS intraday_bars (
        symbol TEXT NOT NULL,
        bar_time TEXT NOT NULL,
        interval TEXT NOT NULL,
        open_price TEXT NOT NULL,
        high_price TEXT NOT NULL,
        low_price TEXT NOT NULL,
        close_price TEXT NOT NULL,
        volume INTEGER NOT NULL,
        amount TEXT NOT NULL,
        source TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (symbol, bar_time, interval)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS latest_quotes (
        symbol TEXT PRIMARY KEY,
        quote_time TEXT NOT NULL,
        last_price TEXT NOT NULL,
        change_amount TEXT NOT NULL,
        pct_change TEXT NOT NULL,
        open_price TEXT NOT NULL,
        high_price TEXT NOT NULL,
        low_price TEXT NOT NULL,
        prev_close TEXT NOT NULL,
        volume INTEGER NOT NULL,
        amount TEXT NOT NULL,
        turnover_rate TEXT,
        source TEXT NOT NULL,
        delay_seconds INTEGER NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS order_books (
        symbol TEXT NOT NULL,
        quote_time TEXT NOT NULL,
        side TEXT NOT NULL,
        level INTEGER NOT NULL,
        price TEXT,
        quantity INTEGER,
        source TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (symbol, quote_time, side, level)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS strategies (
        strategy_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        status TEXT NOT NULL,
        parameters_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS strategy_runs (
        run_id TEXT PRIMARY KEY,
        strategy_id TEXT NOT NULL,
        mode TEXT NOT NULL,
        status TEXT NOT NULL,
        started_at TEXT NOT NULL,
        ended_at TEXT,
        message TEXT,
        FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS signals (
        signal_id TEXT PRIMARY KEY,
        strategy_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        signal_time TEXT NOT NULL,
        market_time TEXT NOT NULL,
        source TEXT NOT NULL,
        direction TEXT NOT NULL,
        strength TEXT NOT NULL,
        reason TEXT NOT NULL,
        suggested_position_pct TEXT NOT NULL DEFAULT '0',
        account_id TEXT,
        scheduled_for TEXT,
        dispatch_status TEXT NOT NULL DEFAULT 'not_scheduled',
        order_id TEXT,
        dispatch_message TEXT NOT NULL DEFAULT '',
        processed_at TEXT,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS accounts (
        account_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        initial_cash TEXT NOT NULL,
        cash TEXT NOT NULL,
        total_assets TEXT NOT NULL,
        peak_total_assets TEXT NOT NULL,
        current_drawdown TEXT NOT NULL DEFAULT '0',
        max_drawdown TEXT NOT NULL DEFAULT '0',
        cumulative_fees TEXT NOT NULL DEFAULT '0',
        risk_status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS positions (
        account_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        name TEXT NOT NULL DEFAULT '',
        quantity INTEGER NOT NULL,
        available_quantity INTEGER NOT NULL,
        cost_price TEXT NOT NULL,
        market_value TEXT NOT NULL,
        last_price TEXT,
        last_buy_date TEXT,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (account_id, symbol)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        account_id TEXT NOT NULL,
        signal_id TEXT,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        order_type TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        limit_price TEXT,
        status TEXT NOT NULL,
        reason TEXT,
        eligible_at TEXT,
        filled_quantity INTEGER NOT NULL DEFAULT 0,
        remaining_quantity INTEGER NOT NULL,
        submitted_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS order_events (
        event_id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL,
        status TEXT NOT NULL,
        event_time TEXT NOT NULL,
        reason TEXT NOT NULL,
        filled_quantity INTEGER NOT NULL,
        remaining_quantity INTEGER NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(order_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS fills (
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
        market_impact TEXT NOT NULL,
        reference_price TEXT,
        degraded_model INTEGER NOT NULL DEFAULT 0,
        filled_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS portfolio_snapshots (
        account_id TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        snapshot_time TEXT NOT NULL,
        cash TEXT NOT NULL,
        market_value TEXT NOT NULL,
        total_assets TEXT NOT NULL,
        net_value TEXT NOT NULL,
        peak_total_assets TEXT NOT NULL,
        current_drawdown TEXT NOT NULL,
        daily_pnl TEXT NOT NULL,
        cumulative_return TEXT NOT NULL,
        max_drawdown TEXT NOT NULL,
        cumulative_fees TEXT NOT NULL,
        PRIMARY KEY (account_id, trade_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS risk_events (
        event_id TEXT PRIMARY KEY,
        account_id TEXT NOT NULL,
        event_time TEXT NOT NULL,
        event_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        message TEXT NOT NULL,
        resolved_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_runs (
        run_id TEXT PRIMARY KEY,
        strategy_id TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        benchmark TEXT NOT NULL,
        initial_cash TEXT NOT NULL,
        status TEXT NOT NULL,
        assumptions TEXT NOT NULL,
        created_at TEXT NOT NULL,
        completed_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_metrics (
        run_id TEXT PRIMARY KEY,
        total_return TEXT,
        annual_return TEXT,
        max_drawdown TEXT,
        sharpe_ratio TEXT,
        sortino_ratio TEXT,
        calmar_ratio TEXT,
        volatility TEXT,
        win_rate TEXT,
        turnover TEXT,
        cost_impact TEXT,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app_settings (
        setting_key TEXT PRIMARY KEY,
        setting_value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS data_quality_reports (
        report_id TEXT PRIMARY KEY,
        provider TEXT NOT NULL,
        checked_at TEXT NOT NULL,
        target TEXT NOT NULL,
        status TEXT NOT NULL,
        missing_fields TEXT NOT NULL,
        duplicate_count INTEGER NOT NULL,
        message TEXT NOT NULL
    )
    """,
]

MIGRATION_STATEMENTS = {
    2: [
        "ALTER TABLE positions ADD COLUMN name TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE positions ADD COLUMN last_buy_date TEXT",
    ],
    3: [
        "ALTER TABLE accounts ADD COLUMN peak_total_assets TEXT NOT NULL DEFAULT '0'",
        "ALTER TABLE accounts ADD COLUMN current_drawdown TEXT NOT NULL DEFAULT '0'",
        "ALTER TABLE accounts ADD COLUMN cumulative_fees TEXT NOT NULL DEFAULT '0'",
        "UPDATE accounts SET peak_total_assets = "
        "CASE WHEN CAST(total_assets AS REAL) > CAST(initial_cash AS REAL) "
        "THEN total_assets ELSE initial_cash END",
        "ALTER TABLE orders ADD COLUMN eligible_at TEXT",
        "ALTER TABLE orders ADD COLUMN filled_quantity INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE orders ADD COLUMN remaining_quantity INTEGER",
        "UPDATE orders SET filled_quantity = COALESCE("
        "(SELECT SUM(fills.quantity) FROM fills WHERE fills.order_id = orders.order_id), 0)",
        "UPDATE orders SET remaining_quantity = quantity - filled_quantity",
        "UPDATE orders SET status = '可撮合' WHERE status IN ('待提交', '待成交')",
        "ALTER TABLE fills ADD COLUMN market_impact TEXT NOT NULL DEFAULT '0'",
        "ALTER TABLE fills ADD COLUMN reference_price TEXT",
        "UPDATE fills SET reference_price = price WHERE reference_price IS NULL",
        "ALTER TABLE portfolio_snapshots ADD COLUMN trade_date TEXT",
        "ALTER TABLE portfolio_snapshots ADD COLUMN net_value TEXT NOT NULL DEFAULT '1'",
        "ALTER TABLE portfolio_snapshots ADD COLUMN peak_total_assets TEXT NOT NULL DEFAULT '0'",
        "ALTER TABLE portfolio_snapshots ADD COLUMN current_drawdown TEXT NOT NULL DEFAULT '0'",
        "ALTER TABLE portfolio_snapshots ADD COLUMN cumulative_fees TEXT NOT NULL DEFAULT '0'",
        "UPDATE portfolio_snapshots SET trade_date = substr(snapshot_time, 1, 10) "
        "WHERE trade_date IS NULL",
        "DELETE FROM portfolio_snapshots WHERE rowid NOT IN ("
        "SELECT MAX(rowid) FROM portfolio_snapshots GROUP BY account_id, trade_date)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_portfolio_snapshot_day "
        "ON portfolio_snapshots(account_id, trade_date)",
        "INSERT OR IGNORE INTO order_events ("
        "event_id, order_id, status, event_time, reason, filled_quantity, remaining_quantity"
        ") SELECT 'LEGACY-' || order_id, order_id, status, updated_at, "
        "COALESCE(reason, 'v3迁移'), filled_quantity, remaining_quantity FROM orders",
    ],
    4: [
        "ALTER TABLE signals ADD COLUMN suggested_position_pct "
        "TEXT NOT NULL DEFAULT '0'",
        "ALTER TABLE signals ADD COLUMN account_id TEXT",
        "ALTER TABLE signals ADD COLUMN scheduled_for TEXT",
        "ALTER TABLE signals ADD COLUMN dispatch_status "
        "TEXT NOT NULL DEFAULT 'not_scheduled'",
        "ALTER TABLE signals ADD COLUMN order_id TEXT",
        "ALTER TABLE signals ADD COLUMN dispatch_message TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE signals ADD COLUMN processed_at TEXT",
        "ALTER TABLE orders ADD COLUMN signal_id TEXT",
    ],
}

POST_MIGRATION_STATEMENTS = [
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_signal_id "
    "ON orders(signal_id) WHERE signal_id IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_signals_dispatch "
    "ON signals(account_id, dispatch_status, scheduled_for)",
]
