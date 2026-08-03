from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME, DISCLAIMER, RefreshSettings, TradingCostSettings, TradingRules
from app.data.providers import Instrument, Quote
from app.models import OrderSide
from app.services.startup import dependency_status
from app.services.trading_app_service import ManualOrderResult, TradingAppService
from app.ui.background_task import BackgroundTask


class QuantMainWindow(QMainWindow):
    """A股量化模拟交易系统主窗口。"""

    def __init__(self, service: TradingAppService | None = None) -> None:
        super().__init__()

        self.rules = TradingRules()
        self.costs = TradingCostSettings()
        self.refresh = RefreshSettings()
        self.service = service or TradingAppService()
        self.dependencies = dependency_status()
        self.market_thread_pool = QThreadPool(self)
        self._quote_refresh_running = False
        self._instrument_refresh_running = False
        self.metric_value_labels: dict[str, QLabel] = {}
        self.metric_detail_labels: dict[str, QLabel] = {}

        self.setWindowTitle(APP_NAME)
        self.resize(1360, 820)
        self.setMinimumSize(1100, 680)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_dashboard_page(), "总览仪表盘")
        self.tabs.addTab(self.create_realtime_quotes_page(), "实时行情")
        self.tabs.addTab(self.create_market_data_page(), "市场数据")
        self.tabs.addTab(self.create_strategy_page(), "策略中心")
        self.tabs.addTab(self.create_selection_page(), "选股结果")
        self.tabs.addTab(self.create_backtest_page(), "历史回测")
        self.tabs.addTab(self.create_trading_page(), "模拟交易")
        self.tabs.addTab(self.create_compare_page(), "策略对比")
        self.tabs.addTab(self.create_settings_page(), "系统设置")
        self.tabs.addTab(self.create_diagnostics_page(), "日志与诊断")
        self.setCentralWidget(self.tabs)

        self.configure_status_bar()
        self.market_refresh_timer = QTimer(self)
        self.market_refresh_timer.setInterval(self.refresh.watchlist_seconds * 1000)
        self.market_refresh_timer.timeout.connect(self.refresh_quote_table)
        if self.service.background_market_data:
            self.market_refresh_timer.start()
            QTimer.singleShot(0, self.refresh_quote_table)
            QTimer.singleShot(0, self.refresh_instruments_async)

    def configure_status_bar(self) -> None:
        status_bar = QStatusBar()
        status_bar.showMessage(
            f"系统就绪 | 模拟资金：{self.format_money(self.rules.initial_cash)} | "
            f"单股上限：{self.format_pct(self.rules.max_single_position_pct)} | "
            f"最大回撤暂停：{self.format_pct(self.rules.max_drawdown_pct)}"
        )
        disclaimer = QLabel(DISCLAIMER)
        disclaimer.setObjectName("disclaimerLabel")
        status_bar.addPermanentWidget(disclaimer, 1)
        self.setStatusBar(status_bar)

    def create_dashboard_page(self) -> QWidget:
        page = self.create_page()
        layout = page.layout()
        metrics = self.service.get_dashboard_metrics()
        cards = [
            ("市场状态", metrics["market_status"], "当前运行模式"),
            ("数据源连接", metrics["data_source"], metrics["data_status"]),
            ("行情延迟", metrics["quote_delay"], "按行情时间戳计算"),
            ("账户总资产", metrics["account_total"], "本地模拟账户"),
            ("可用现金", metrics["cash"], "账户实时状态"),
            ("持仓市值", metrics["market_value"], "按当前行情估值"),
            ("当前回撤", metrics["current_drawdown"], "相对历史净值峰值"),
            ("最大回撤", metrics["max_drawdown"], "账户历史最大值"),
            ("累计费用", metrics["cumulative_fees"], "含显式费用与价格影响"),
            ("账户存储", metrics["persistence_status"], "SQLite本地持久化"),
            ("风控状态", metrics["risk_status"], "回撤达到15%暂停买入"),
            ("运行策略", metrics["running_strategy"], self.service.market_data.name),
        ]
        grid = QGridLayout()
        grid.setSpacing(12)
        for index, (title, value, detail) in enumerate(cards):
            grid.addWidget(self.create_metric_card(title, value, detail), index // 4, index % 4)
        layout.addLayout(grid)
        layout.addWidget(
            self.wrap_group(
                "最近信号和订单",
                self.create_table(
                    self.order_headers(),
                    self.order_rows(limit=5),
                ),
            )
        )
        return page

    def create_realtime_quotes_page(self) -> QWidget:
        page = self.create_page()
        layout = page.layout()
        search_row = QHBoxLayout()
        search_label = QLabel("搜索")
        search_label.setObjectName("fieldLabel")
        search_input = QLineEdit()
        search_input.setPlaceholderText("输入股票代码或名称")
        refresh_button = QPushButton("刷新自选股")
        refresh_button.clicked.connect(self.refresh_quote_table)
        search_row.addWidget(search_label)
        search_row.addWidget(search_input, 1)
        search_row.addWidget(refresh_button)
        layout.addLayout(search_row)

        self.quote_table = self.create_table(self.quote_headers(), self.quote_rows())
        layout.addWidget(self.wrap_group("自选股行情", self.quote_table))
        layout.addWidget(
            self.create_notice(
                "五档买卖量是未成交委托量，不是主动买卖成交量；委比、委差缺失时显示数据源不支持。"
            )
        )
        return page

    def create_market_data_page(self) -> QWidget:
        page = self.create_page()
        layout = page.layout()
        layout.addWidget(
            self.create_rule_summary(
                [
                    ("股票池", "沪深A股，第一版默认不含北交所"),
                    ("排除规则", f"ST / 退市整理 / 上市不足{self.rules.min_listing_days}日"),
                    ("数据源", self.service.market_data.name),
                    ("数据质量", "字段校验已接入服务层"),
                ]
            )
        )
        self.instrument_table = self.create_table(
            ["代码", "名称", "交易所", "上市日期", "行业", "交易状态", "是否纳入", "说明"],
            self.instrument_rows(),
        )
        layout.addWidget(self.wrap_group("股票池过滤预览", self.instrument_table))
        return page

    def create_strategy_page(self) -> QWidget:
        page = self.create_page()
        layout = page.layout()
        selector_row = QHBoxLayout()
        selector_label = QLabel("当前策略")
        selector_label.setObjectName("fieldLabel")
        selector = QComboBox()
        strategy_names = ["均线趋势", "动量选股", "低估值因子", "盘口与量价演示"]
        selector.addItems(strategy_names)
        selector.setMinimumWidth(230)
        for label in ("启动", "暂停", "停止"):
            button = QPushButton(label)
            button.setEnabled(False)
            selector_row.addWidget(button)
        preview_button = QPushButton("生成收盘信号预览")
        preview_button.clicked.connect(self.generate_signal_preview)
        selector_row.insertWidget(0, selector)
        selector_row.insertWidget(0, selector_label)
        selector_row.addStretch()
        selector_row.addWidget(preview_button)
        layout.addLayout(selector_row)

        rows = self.strategy_status_rows()
        self.strategy_table = self.create_table(["策略", "状态", "最近运行", "信号数"], rows)
        layout.addWidget(self.wrap_group("内置策略库", self.strategy_table))
        return page

    def create_selection_page(self) -> QWidget:
        page = self.create_page()
        layout = page.layout()
        export_row = QHBoxLayout()
        export_row.addStretch()
        export_button = QPushButton("导出CSV")
        export_button.setEnabled(False)
        export_row.addWidget(export_button)
        layout.addLayout(export_row)
        self.selection_table = self.create_table(
            ["策略", "代码", "名称", "评分", "入选原因", "信号时间", "建议仓位", "风控后仓位"],
            self.selection_rows(),
        )
        layout.addWidget(self.wrap_group("选股结果", self.selection_table))
        return page

    def create_backtest_page(self) -> QWidget:
        page = self.create_page()
        layout = page.layout()
        control_row = QHBoxLayout()
        start_button = QPushButton("开始回测")
        cancel_button = QPushButton("取消回测")
        start_button.setEnabled(False)
        cancel_button.setEnabled(False)
        control_row.addWidget(QLabel(f"默认周期：最近{self.rules.backtest_years}年"))
        control_row.addWidget(QLabel(f"基准：{self.rules.benchmark}"))
        control_row.addStretch()
        control_row.addWidget(start_button)
        control_row.addWidget(cancel_button)
        layout.addLayout(control_row)
        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setFormat("尚未开始")
        layout.addWidget(self.wrap_group("回测进度", progress))
        result = self.service.run_demo_backtest()
        rows = [
            [
                result.strategy_name,
                self.rules.benchmark,
                self.format_pct(result.total_return),
                self.service.market_data.name,
                "尚未计算",
                f"成交{len(result.trades)}笔",
            ]
        ]
        layout.addWidget(
            self.wrap_group(
                "回测绩效",
                self.create_table(["策略", "基准", "总收益", "年化", "最大回撤", "状态"], rows),
            )
        )
        return page

    def create_trading_page(self) -> QWidget:
        page = self.create_page()
        layout = page.layout()
        layout.addWidget(
            self.create_rule_summary(
                [
                    ("模拟性质", "内部模拟订单，不连接券商"),
                    ("买入规则", f"普通A股{self.rules.buy_lot_size}股整数倍"),
                    ("T+1", "当日买入当日不可卖出"),
                    ("风控", "回撤15%暂停新增买入，仍允许卖出"),
                    ("当前回撤", self.format_pct(self.service.account.current_drawdown)),
                    ("最大回撤", self.format_pct(self.service.account.max_drawdown)),
                    ("累计费用", self.format_money(self.service.account.cumulative_fees)),
                ]
            )
        )
        layout.addWidget(self.create_manual_order_group())

        self.positions_table = self.create_table(self.position_headers(), self.position_rows())
        self.orders_table = self.create_table(self.order_headers(), self.order_rows())
        self.fills_table = self.create_table(self.fill_headers(), self.fill_rows())
        layout.addWidget(self.wrap_group("当前持仓", self.positions_table))
        layout.addWidget(self.wrap_group("待成交与历史订单", self.orders_table))
        layout.addWidget(self.wrap_group("成交记录", self.fills_table))
        return page

    def create_compare_page(self) -> QWidget:
        page = self.create_page()
        layout = page.layout()
        result = self.service.run_demo_backtest()
        rows = [
            [
                result.strategy_name,
                self.rules.benchmark,
                self.format_pct(result.total_return),
                self.service.market_data.name,
                "尚未计算",
                "尚未计算",
                "尚未计算",
                f"成交{len(result.trades)}笔",
            ]
        ]
        layout.addWidget(
            self.wrap_group(
                "策略横向比较",
                self.create_table(
                    ["策略", "基准", "总收益", "年化", "最大回撤", "夏普", "胜率", "状态"], rows
                ),
            )
        )
        return page

    def create_settings_page(self) -> QWidget:
        page = self.create_page()
        layout = page.layout()
        cost_rows = [
            ["买卖佣金", str(self.costs.commission_rate), "集中配置"],
            ["最低佣金", self.format_money(self.costs.min_commission), "集中配置"],
            ["卖出印花税", str(self.costs.stamp_tax_rate), "集中配置"],
            ["过户费", str(self.costs.transfer_fee_rate), "集中配置"],
            ["滑点", f"{self.costs.slippage_bps} bps", "集中配置"],
            ["市场冲击", f"{self.costs.market_impact_bps} bps", "集中配置"],
            [
                "成交量参与率上限",
                self.format_pct(self.costs.max_volume_participation),
                "撮合内核已使用",
            ],
        ]
        refresh_rows = [
            ["自选股刷新", f"{self.refresh.watchlist_seconds}秒", "后台线程阶段后续优化"],
            ["监控股票刷新", f"{self.refresh.monitor_seconds}秒", "后台线程阶段后续优化"],
            ["网络超时", f"{self.refresh.request_timeout_seconds}秒", "真实数据源接入时使用"],
            ["最大重试", str(self.refresh.max_retries), "真实数据源接入时使用"],
        ]
        layout.addWidget(
            self.wrap_group(
                "交易成本假设", self.create_table(["项目", "当前值", "说明"], cost_rows)
            )
        )
        layout.addWidget(
            self.wrap_group(
                "行情刷新与网络", self.create_table(["项目", "当前值", "说明"], refresh_rows)
            )
        )
        return page

    def create_diagnostics_page(self) -> QWidget:
        page = self.create_page()
        layout = page.layout()
        dependency_rows = [
            [name, "已安装" if installed else "未安装", "依赖探查"]
            for name, installed in self.dependencies.items()
        ]
        layout.addWidget(
            self.wrap_group(
                "依赖状态", self.create_table(["依赖", "状态", "说明"], dependency_rows)
            )
        )
        log_view = QTextEdit()
        log_view.setReadOnly(True)
        log_view.setMinimumHeight(130)
        log_view.setText(
            f"日志文件：logs/quant_app.log\n当前行情源：{self.service.market_data.name}\n"
            "账户、风控和撮合内核已接入UI服务层。\n"
            "诊断导出尚未实现，导出内容必须过滤Token、Cookie和敏感字段。"
        )
        layout.addWidget(self.wrap_group("日志预览", log_view))
        return page

    def create_manual_order_group(self) -> QGroupBox:
        order_box = QGroupBox("手工模拟下单")
        order_layout = QGridLayout(order_box)
        self.symbol_input = QLineEdit("000001.SZ")
        self.price_input = QDoubleSpinBox()
        self.price_input.setMaximum(9999.99)
        self.price_input.setDecimals(2)
        self.price_input.setValue(10.80)
        self.quantity_input = QSpinBox()
        self.quantity_input.setMaximum(1_000_000)
        self.quantity_input.setSingleStep(100)
        self.quantity_input.setValue(100)
        buy_button = QPushButton("模拟买入")
        sell_button = QPushButton("模拟卖出")
        buy_button.clicked.connect(lambda: self.execute_manual_order(OrderSide.BUY))
        sell_button.clicked.connect(lambda: self.execute_manual_order(OrderSide.SELL))
        order_layout.addWidget(QLabel("代码"), 0, 0)
        order_layout.addWidget(self.symbol_input, 0, 1)
        order_layout.addWidget(QLabel("限价"), 0, 2)
        order_layout.addWidget(self.price_input, 0, 3)
        order_layout.addWidget(QLabel("数量"), 0, 4)
        order_layout.addWidget(self.quantity_input, 0, 5)
        order_layout.addWidget(buy_button, 0, 6)
        order_layout.addWidget(sell_button, 0, 7)
        warning = QLabel(DISCLAIMER)
        warning.setObjectName("statusPending")
        order_layout.addWidget(warning, 1, 0, 1, 8)
        return order_box

    def execute_manual_order(
        self,
        side: OrderSide,
        symbol: str | None = None,
        quantity: int | None = None,
        limit_price: Decimal | None = None,
        confirm: bool = True,
    ) -> ManualOrderResult:
        target_symbol = symbol or self.symbol_input.text().strip()
        target_quantity = quantity or self.quantity_input.value()
        target_price = (
            limit_price if limit_price is not None else Decimal(str(self.price_input.value()))
        )
        if confirm:
            reply = QMessageBox.question(
                self,
                "确认模拟下单",
                f"确认{side.value} {target_symbol} {target_quantity}股？\n{DISCLAIMER}",
            )
            if reply != QMessageBox.StandardButton.Yes:
                result = ManualOrderResult(False, None, None, "用户取消")
                self.statusBar().showMessage(result.message)
                return result
        result = self.service.place_manual_order(side, target_symbol, target_quantity, target_price)
        self.statusBar().showMessage(result.message)
        self.refresh_trading_tables()
        self._update_dashboard_metrics()
        self.refresh_quote_table()
        return result

    def refresh_quote_table(self) -> None:
        if not self.service.background_market_data:
            if hasattr(self, "quote_table"):
                self.set_table_rows(self.quote_table, self.quote_rows())
            return
        if self._quote_refresh_running:
            return
        self._quote_refresh_running = True
        self.statusBar().showMessage("正在后台刷新真实自选股行情...")
        task = BackgroundTask(self.service.refresh_watchlist_market_data)
        task.signals.result.connect(self._on_quotes_refreshed)
        task.signals.error.connect(self._on_market_refresh_error)
        task.signals.finished.connect(self._quote_refresh_finished)
        self.market_thread_pool.start(task)

    def refresh_instruments_async(self) -> None:
        if not self.service.background_market_data or self._instrument_refresh_running:
            return
        self._instrument_refresh_running = True
        task = BackgroundTask(self.service.refresh_instruments)
        task.signals.result.connect(self._on_instruments_refreshed)
        task.signals.error.connect(self._on_market_refresh_error)
        task.signals.finished.connect(self._instrument_refresh_finished)
        self.market_thread_pool.start(task)

    def _on_quotes_refreshed(self, quotes: object) -> None:
        if hasattr(self, "quote_table"):
            self.set_table_rows(self.quote_table, self.quote_rows())
        self._update_dashboard_metrics()
        count = len(quotes) if isinstance(quotes, list) else 0
        self.statusBar().showMessage(f"真实行情后台刷新完成：{count}只")

    def _on_instruments_refreshed(self, instruments: object) -> None:
        if hasattr(self, "instrument_table"):
            self.set_table_rows(self.instrument_table, self.instrument_rows())
        count = len(instruments) if isinstance(instruments, list) else 0
        self.statusBar().showMessage(f"沪深A股主表后台加载完成：{count}只")

    def _on_market_refresh_error(self, message: str) -> None:
        self.service.record_market_error(message)
        self._update_dashboard_metrics()
        self.statusBar().showMessage(f"真实行情刷新失败：{message}")

    def _update_dashboard_metrics(self) -> None:
        metrics = self.service.get_dashboard_metrics()
        values = {
            "市场状态": metrics["market_status"],
            "数据源连接": metrics["data_source"],
            "行情延迟": metrics["quote_delay"],
            "账户总资产": metrics["account_total"],
            "可用现金": metrics["cash"],
            "持仓市值": metrics["market_value"],
            "当前回撤": metrics["current_drawdown"],
            "最大回撤": metrics["max_drawdown"],
            "累计费用": metrics["cumulative_fees"],
            "账户存储": metrics["persistence_status"],
            "风控状态": metrics["risk_status"],
            "运行策略": metrics["running_strategy"],
        }
        for title, value in values.items():
            label = self.metric_value_labels.get(title)
            if label is not None:
                label.setText(value)
        data_status_label = self.metric_detail_labels.get("数据源连接")
        if data_status_label is not None:
            data_status_label.setText(metrics["data_status"])

    def _quote_refresh_finished(self) -> None:
        self._quote_refresh_running = False

    def _instrument_refresh_finished(self) -> None:
        self._instrument_refresh_running = False

    def refresh_trading_tables(self) -> None:
        if hasattr(self, "positions_table"):
            self.set_table_rows(self.positions_table, self.position_rows())
        if hasattr(self, "orders_table"):
            self.set_table_rows(self.orders_table, self.order_rows())
        if hasattr(self, "fills_table"):
            self.set_table_rows(self.fills_table, self.fill_rows())

    def generate_signal_preview(self) -> None:
        signals = self.service.strategy_service.run_daily_signals(["000001.SZ", "300750.SZ"])
        self.statusBar().showMessage(
            f"已使用{self.service.market_data.name}生成{len(signals)}条策略信号"
        )
        if hasattr(self, "selection_table"):
            self.set_table_rows(self.selection_table, self.selection_rows())
            self.selection_table.selectRow(0)
        if hasattr(self, "strategy_table"):
            self.set_table_rows(self.strategy_table, self.strategy_status_rows())

    def strategy_status_rows(self) -> list[list[str]]:
        return [
            [status.name, status.state.value, status.last_run, str(status.signal_count)]
            for status in self.service.strategy_service.statuses()
        ]

    def selection_rows(self) -> list[list[str]]:
        signals = self.service.strategy_service.latest_signals
        if not signals:
            return [["尚无信号", "-", "-", "-", "点击策略中心生成信号", "-", "-", "-"]]
        name_map = {quote.symbol: quote.name for quote in self.service.get_watchlist_quotes()}
        return [
            [
                signal.strategy_name,
                signal.symbol,
                name_map.get(signal.symbol, signal.symbol),
                str(signal.strength),
                signal.reason,
                signal.signal_time.strftime("%Y-%m-%d %H:%M:%S"),
                self.format_pct(signal.suggested_position_pct),
                self.format_pct(signal.suggested_position_pct),
            ]
            for signal in signals
        ]

    def quote_headers(self) -> list[str]:
        return [
            "代码",
            "名称",
            "最新价",
            "涨跌额",
            "涨跌幅",
            "今开",
            "最高",
            "最低",
            "昨收",
            "成交量",
            "成交额",
            "换手率",
            "行情时间",
            "数据源",
        ]

    def quote_rows(self) -> list[list[str]]:
        quotes = self.service.get_watchlist_quotes()
        if not quotes:
            return [
                [
                    "-",
                    "等待后台刷新",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "-",
                    "0",
                    "¥0.00",
                    "数据源不支持",
                    "-",
                    self.service.market_data.name,
                ]
            ]
        return [self.quote_row(quote) for quote in quotes]

    def quote_row(self, quote: Quote) -> list[str]:
        return [
            quote.symbol,
            quote.name,
            str(quote.last_price),
            str(quote.change_amount),
            self.format_pct(quote.pct_change),
            str(quote.open_price),
            str(quote.high_price),
            str(quote.low_price),
            str(quote.prev_close),
            f"{quote.volume:,}",
            self.format_money(quote.amount),
            self.format_pct(quote.turnover_rate or Decimal("0")),
            quote.quote_time.strftime("%Y-%m-%d %H:%M:%S"),
            f"{quote.source} / 延迟{quote.delay_seconds}秒",
        ]

    def instrument_rows(self) -> list[list[str]]:
        rows: list[list[str]] = []
        instruments = self.service.get_instruments()
        if not instruments:
            return [["-", "等待后台加载", "-", "-", "数据源不支持", "-", "-", "-"]]
        for instrument in instruments:
            rows.append(
                [
                    instrument.symbol,
                    instrument.name,
                    instrument.exchange,
                    instrument.listed_date.isoformat(),
                    instrument.industry or "数据源不支持",
                    "停牌" if instrument.is_suspended else "正常",
                    "否"
                    if instrument.is_st or instrument.is_delisting or instrument.is_delisted
                    else "是",
                    self.instrument_note(instrument),
                ]
            )
        return rows

    def instrument_note(self, instrument: Instrument) -> str:
        if instrument.is_st:
            return "排除ST"
        if instrument.is_delisting:
            return "排除退市整理"
        if instrument.is_delisted:
            return "排除已退市"
        if not instrument.is_eligible(self.service.clock.today()):
            return f"排除上市不足{TradingRules().min_listing_days}日"
        return "纳入股票池"

    def position_headers(self) -> list[str]:
        return ["代码", "名称", "数量", "今日可卖", "成本价", "最新价", "市值", "浮动盈亏"]

    def position_rows(self) -> list[list[str]]:
        latest_prices = self.service.latest_price_map()
        if not self.service.account.positions:
            return [["-", "-", "0", "0", "-", "-", "¥0.00", "¥0.00"]]
        rows: list[list[str]] = []
        for position in self.service.account.positions.values():
            last_price = latest_prices.get(position.symbol, position.cost_price)
            market_value = position.market_value(last_price)
            pnl = (last_price - position.cost_price) * Decimal(position.quantity)
            rows.append(
                [
                    position.symbol,
                    position.name,
                    str(position.quantity),
                    str(position.available_quantity),
                    str(position.cost_price),
                    str(last_price),
                    self.format_money(market_value),
                    self.format_money(pnl),
                ]
            )
        return rows

    def order_headers(self) -> list[str]:
        return [
            "订单号",
            "代码",
            "方向",
            "类型",
            "数量",
            "已成交",
            "剩余",
            "限价",
            "状态",
            "提交时间",
            "可撮合时间",
            "说明",
        ]

    def order_rows(self, limit: int | None = None) -> list[list[str]]:
        orders = self.service.account.orders[-limit:] if limit else self.service.account.orders
        if not orders:
            return [["-", "-", "-", "-", "0", "0", "0", "-", "尚无订单", "-", "-", "-"]]
        return [
            [
                order.order_id,
                order.symbol,
                order.side.value,
                order.order_type.value,
                str(order.quantity),
                str(order.filled_quantity),
                str(order.remaining_quantity),
                str(order.limit_price or "市价"),
                order.status.value,
                order.submitted_at.strftime("%Y-%m-%d %H:%M:%S"),
                order.eligible_at.strftime("%Y-%m-%d %H:%M:%S")
                if order.eligible_at is not None
                else "-",
                order.reason,
            ]
            for order in reversed(orders)
        ]

    def fill_headers(self) -> list[str]:
        return [
            "成交号",
            "订单号",
            "代码",
            "方向",
            "数量",
            "参考价",
            "成交价",
            "佣金",
            "印花税",
            "过户费",
            "滑点",
            "市场冲击",
            "总成本",
            "成交时间",
            "说明",
        ]

    def fill_rows(self) -> list[list[str]]:
        if not self.service.account.fills:
            return [
                [
                    "-",
                    "-",
                    "-",
                    "-",
                    "0",
                    "-",
                    "-",
                    "¥0.00",
                    "¥0.00",
                    "¥0.00",
                    "¥0.00",
                    "¥0.00",
                    "¥0.00",
                    "-",
                    "-",
                ]
            ]
        rows: list[list[str]] = []
        for fill in reversed(self.service.account.fills):
            total_cost = (
                fill.commission
                + fill.tax
                + fill.transfer_fee
                + fill.slippage
                + fill.market_impact
            )
            rows.append(
                [
                    fill.fill_id,
                    fill.order_id,
                    fill.symbol,
                    fill.side.value,
                    str(fill.quantity),
                    str(fill.reference_price or fill.price),
                    str(fill.price),
                    self.format_money(fill.commission),
                    self.format_money(fill.tax),
                    self.format_money(fill.transfer_fee),
                    self.format_money(fill.slippage),
                    self.format_money(fill.market_impact),
                    self.format_money(total_cost),
                    fill.filled_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "降级撮合" if fill.degraded_model else "正常撮合",
                ]
            )
        return rows

    def create_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        return page

    def create_notice(self, text: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("noticeFrame")
        layout = QHBoxLayout(frame)
        status = QLabel("状态")
        status.setObjectName("statusPending")
        message = QLabel(text)
        message.setObjectName("noticeText")
        message.setWordWrap(True)
        layout.addWidget(status)
        layout.addWidget(message, 1)
        return frame

    def create_rule_summary(self, items: list[tuple[str, str]]) -> QGroupBox:
        group = QGroupBox("核心规则")
        grid = QGridLayout(group)
        grid.setSpacing(10)
        for index, (label, value) in enumerate(items):
            label_widget = QLabel(label)
            label_widget.setObjectName("summaryLabel")
            value_widget = QLabel(value)
            value_widget.setObjectName("summaryValue")
            value_widget.setWordWrap(True)
            grid.addWidget(label_widget, index // 2, (index % 2) * 2)
            grid.addWidget(value_widget, index // 2, (index % 2) * 2 + 1)
        return group

    def create_metric_card(self, title: str, value: str, detail: str) -> QFrame:
        card = QFrame()
        card.setObjectName("metricCard")
        card.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout(card)
        layout.setSpacing(4)
        for text, name in (
            (title, "metricTitle"),
            (value, "metricValue"),
            (detail, "metricDetail"),
        ):
            label = QLabel(text)
            label.setObjectName(name)
            label.setWordWrap(True)
            layout.addWidget(label)
            if name == "metricValue":
                self.metric_value_labels[title] = label
            elif name == "metricDetail":
                self.metric_detail_labels[title] = label
        return card

    def create_table(self, headers: list[str], rows: list[list[str]]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        resize_mode = (
            QHeaderView.ResizeMode.ResizeToContents
            if len(headers) > 10
            else QHeaderView.ResizeMode.Stretch
        )
        table.horizontalHeader().setSectionResizeMode(resize_mode)
        self.set_table_rows(table, rows)
        return table

    def set_table_rows(self, table: QTableWidget, rows: list[list[str]]) -> None:
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row_index, column_index, item)
        table.resizeRowsToContents()

    def wrap_group(self, title: str, widget: QWidget) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.addWidget(widget)
        return group

    @staticmethod
    def format_money(value: Decimal) -> str:
        return f"¥{value:,.2f}"

    @staticmethod
    def format_pct(value: Decimal) -> str:
        return f"{value * Decimal('100'):.2f}%"
