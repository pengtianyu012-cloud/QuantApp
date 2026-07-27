from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
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
    QPushButton,
    QProgressBar,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.config import APP_NAME, DISCLAIMER, RefreshSettings, TradingCostSettings, TradingRules
from app.models import StrategyInfo, built_in_strategy_catalog
from app.services.startup import dependency_status


class QuantMainWindow(QMainWindow):
    """A股量化模拟交易系统主窗口。"""

    def __init__(self) -> None:
        super().__init__()

        self.rules = TradingRules()
        self.costs = TradingCostSettings()
        self.refresh = RefreshSettings()
        self.strategies = built_in_strategy_catalog()
        self.dependencies = dependency_status()

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

    def configure_status_bar(self) -> None:
        status_bar = QStatusBar()
        status_bar.showMessage(
            f"系统就绪 | 模拟资金：{self.format_money(self.rules.initial_cash)} | "
            f"单股上限：{self.format_pct(self.rules.max_single_position_pct)} | "
            f"最大回撤暂停：{self.format_pct(self.rules.max_drawdown_pct)}"
        )
        disclaimer = QLabel(DISCLAIMER)
        disclaimer.setObjectName("disclaimerLabel")
        disclaimer.setWordWrap(False)
        status_bar.addPermanentWidget(disclaimer, 1)
        self.setStatusBar(status_bar)

    def create_dashboard_page(self) -> QWidget:
        page = self.create_page()
        layout = page.layout()

        metrics = QGridLayout()
        metrics.setSpacing(12)
        cards = [
            ("市场状态", "待接入", "阶段2接入交易日历后显示"),
            ("数据源连接", "Mock已实现", "页面接线在阶段4完成"),
            ("行情延迟", "尚未实现", "数据源支持后展示"),
            ("账户总资产", self.format_money(self.rules.initial_cash), "本地模拟账户"),
            ("可用现金", self.format_money(self.rules.initial_cash), "当前未建仓"),
            ("持仓市值", "¥0", "当前无持仓"),
            ("最大回撤", "0.0%", "阈值15%"),
            ("风控状态", "允许买入", "阶段3接入风控引擎"),
        ]
        for index, (title, value, detail) in enumerate(cards):
            metrics.addWidget(self.create_metric_card(title, value, detail), index // 4, index % 4)
        layout.addLayout(metrics)

        layout.addWidget(
            self.wrap_group(
                "最近信号和订单",
                self.create_table(
                    ["时间", "类型", "策略", "代码", "方向", "状态", "说明"],
                    [["-", "尚未实现", "-", "-", "-", "待接入", "阶段3后显示真实模拟订单"]],
                ),
            )
        )
        layout.addWidget(self.create_notice("阶段1仅完成仪表盘结构，行情、账户和风控将在后续阶段接入。"))
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
        refresh_button.setEnabled(False)
        search_row.addWidget(search_label)
        search_row.addWidget(search_input, 1)
        search_row.addWidget(refresh_button)
        layout.addLayout(search_row)

        headers = [
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
            "盘口",
            "内外盘",
            "行情时间",
            "数据源",
        ]
        rows = [
            [
                "600519.SH",
                "贵州茅台",
                "尚未实现",
                "尚未实现",
                "尚未实现",
                "尚未实现",
                "尚未实现",
                "尚未实现",
                "尚未实现",
                "尚未实现",
                "尚未实现",
                "尚未实现",
                "阶段2接入",
                "数据源不支持时显示",
                "-",
                "Mock已实现，页面待接线",
            ]
        ]
        layout.addWidget(self.wrap_group("自选股行情", self.create_table(headers, rows)))
        layout.addWidget(self.create_notice("五档盘口委托量不会被称为实际成交量。"))
        return page

    def create_market_data_page(self) -> QWidget:
        page = self.create_page()
        layout = page.layout()

        layout.addWidget(
            self.create_rule_summary(
                [
                    ("股票池", "沪深A股，第一版默认不含北交所"),
                    ("排除规则", f"ST / 退市整理 / 上市不足{self.rules.min_listing_days}日"),
                    ("全市场刷新", "不做高频全量刷新"),
                    ("数据质量", "阶段2接入校验报告"),
                ]
            )
        )
        table = self.create_table(
            ["代码", "名称", "交易所", "上市日期", "行业", "交易状态", "是否纳入", "说明"],
            [
                ["600519.SH", "贵州茅台", "上交所", "2001-08-27", "食品饮料", "正常", "是", "Mock样例"],
                ["000001.SZ", "平安银行", "深交所", "1991-04-03", "银行", "正常", "是", "Mock样例"],
                ["000000.SZ", "示例ST股", "深交所", "2010-01-01", "示例", "ST", "否", "排除ST"],
                ["301999.SZ", "示例新股", "深交所", "2026-07-01", "示例", "正常", "否", "上市不足60日"],
            ],
        )
        layout.addWidget(self.wrap_group("股票池过滤预览", table))
        return page

    def create_strategy_page(self) -> QWidget:
        page = self.create_page()
        layout = page.layout()

        selector_row = QHBoxLayout()
        selector_label = QLabel("当前策略")
        selector_label.setObjectName("fieldLabel")
        selector = QComboBox()
        selector.addItems([strategy.name for strategy in self.strategies])
        selector.setMinimumWidth(230)
        start_button = QPushButton("启动")
        pause_button = QPushButton("暂停")
        stop_button = QPushButton("停止")
        for button in (start_button, pause_button, stop_button):
            button.setEnabled(False)
        preview_button = QPushButton("生成收盘信号预览")
        preview_button.clicked.connect(self.generate_signal_preview)

        selector_row.addWidget(selector_label)
        selector_row.addWidget(selector)
        selector_row.addStretch()
        selector_row.addWidget(start_button)
        selector_row.addWidget(pause_button)
        selector_row.addWidget(stop_button)
        selector_row.addWidget(preview_button)
        layout.addLayout(selector_row)

        rows = [
            [
                strategy.name,
                strategy.description,
                strategy.signal_rule,
                strategy.risk_note,
                strategy.stage,
                strategy.status,
            ]
            for strategy in self.strategies
        ]
        layout.addWidget(
            self.wrap_group(
                "内置策略库",
                self.create_table(["策略", "核心逻辑", "信号生成", "风控关注", "阶段", "状态"], rows),
            )
        )

        notes = QTextEdit()
        notes.setReadOnly(True)
        notes.setMinimumHeight(120)
        notes.setText(
            "开发记录\n"
            "1. 阶段1只登记策略目录和参数入口。\n"
            "2. 阶段5接入Strategy基类、生命周期和真实信号。\n"
            "3. 未完成的策略状态均显示为尚未实现。"
        )
        layout.addWidget(self.wrap_group("学习与开发同步记录", notes))
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
            [["尚未实现", "-", "-", "-", "阶段5接入策略信号", "-", "-", "-"]],
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

        table = self.create_table(
            ["策略", "总收益率", "年化收益", "最大回撤", "夏普比率", "交易次数", "状态"],
            [[strategy.name, "-", "-", "-", "-", "-", "尚未实现"] for strategy in self.strategies],
        )
        layout.addWidget(self.wrap_group("回测绩效", table))
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
                ]
            )
        )

        order_box = QGroupBox("手工模拟下单")
        order_layout = QGridLayout(order_box)
        symbol_input = QLineEdit()
        symbol_input.setPlaceholderText("股票代码")
        price_input = QDoubleSpinBox()
        price_input.setMaximum(9999.99)
        price_input.setDecimals(2)
        quantity_input = QSpinBox()
        quantity_input.setMaximum(1_000_000)
        quantity_input.setSingleStep(100)
        buy_button = QPushButton("模拟买入")
        sell_button = QPushButton("模拟卖出")
        for widget in (symbol_input, price_input, quantity_input, buy_button, sell_button):
            widget.setEnabled(False)
        order_layout.addWidget(QLabel("代码"), 0, 0)
        order_layout.addWidget(symbol_input, 0, 1)
        order_layout.addWidget(QLabel("限价"), 0, 2)
        order_layout.addWidget(price_input, 0, 3)
        order_layout.addWidget(QLabel("数量"), 0, 4)
        order_layout.addWidget(quantity_input, 0, 5)
        order_layout.addWidget(buy_button, 0, 6)
        order_layout.addWidget(sell_button, 0, 7)
        layout.addWidget(order_box)

        positions = self.create_table(
            ["代码", "名称", "数量", "今日可卖", "成本价", "最新价", "市值", "浮动盈亏"],
            [["-", "-", "0", "0", "-", "-", "¥0", "¥0"]],
        )
        orders = self.create_table(
            ["订单号", "代码", "方向", "数量", "价格", "状态", "说明"],
            [["-", "-", "-", "-", "-", "尚未实现", "核心已实现，页面阶段4接线"]],
        )
        layout.addWidget(self.wrap_group("当前持仓", positions))
        layout.addWidget(self.wrap_group("待成交订单", orders))
        return page

    def create_compare_page(self) -> QWidget:
        page = self.create_page()
        layout = page.layout()

        table = self.create_table(
            [
                "策略",
                "基准",
                "总收益率",
                "年化收益",
                "最大回撤",
                "夏普",
                "胜率",
                "换手率",
                "成本影响",
                "状态",
            ],
            [[strategy.name, self.rules.benchmark, "-", "-", "-", "-", "-", "-", "-", "尚未实现"] for strategy in self.strategies],
        )
        layout.addWidget(self.wrap_group("策略横向比较", table))
        return page

    def create_settings_page(self) -> QWidget:
        page = self.create_page()
        layout = page.layout()

        cost_rows = [
            ["买卖佣金", str(self.costs.commission_rate), "集中配置，后续可在UI修改"],
            ["最低佣金", self.format_money(self.costs.min_commission), "集中配置"],
            ["卖出印花税", str(self.costs.stamp_tax_rate), "集中配置"],
            ["过户费", str(self.costs.transfer_fee_rate), "集中配置"],
            ["滑点", f"{self.costs.slippage_bps} bps", "集中配置"],
            ["市场冲击", f"{self.costs.market_impact_bps} bps", "集中配置"],
            ["成交量参与率上限", self.format_pct(self.costs.max_volume_participation), "集中配置"],
        ]
        refresh_rows = [
            ["自选股刷新", f"{self.refresh.watchlist_seconds}秒", "后台线程接入阶段4"],
            ["监控股票刷新", f"{self.refresh.monitor_seconds}秒", "后台线程接入阶段4"],
            ["网络超时", f"{self.refresh.request_timeout_seconds}秒", "数据源适配器阶段2"],
            ["最大重试", str(self.refresh.max_retries), "指数退避阶段2"],
        ]
        layout.addWidget(self.wrap_group("交易成本假设", self.create_table(["项目", "当前值", "说明"], cost_rows)))
        layout.addWidget(self.wrap_group("行情刷新与网络", self.create_table(["项目", "当前值", "说明"], refresh_rows)))
        return page

    def create_diagnostics_page(self) -> QWidget:
        page = self.create_page()
        layout = page.layout()

        dependency_rows = [
            [name, "已安装" if installed else "未安装", "阶段1依赖探查"]
            for name, installed in self.dependencies.items()
        ]
        layout.addWidget(self.wrap_group("依赖状态", self.create_table(["依赖", "状态", "说明"], dependency_rows)))

        log_view = QTextEdit()
        log_view.setReadOnly(True)
        log_view.setMinimumHeight(130)
        log_view.setText(
            "日志文件：logs/quant_app.log\n"
            "阶段1已配置滚动日志。后续数据源、策略、订单和风控日志会接入本页。\n"
            "诊断导出尚未实现，导出内容必须过滤Token、Cookie和敏感字段。"
        )
        layout.addWidget(self.wrap_group("日志预览", log_view))
        return page

    def generate_signal_preview(self) -> None:
        self.statusBar().showMessage("已生成界面预览 | 真实策略信号尚未实现")
        if hasattr(self, "selection_table"):
            self.selection_table.selectRow(0)

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
        status = QLabel("尚未实现")
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

        title_label = QLabel(title)
        title_label.setObjectName("metricTitle")
        value_label = QLabel(value)
        value_label.setObjectName("metricValue")
        detail_label = QLabel(detail)
        detail_label.setObjectName("metricDetail")
        detail_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(detail_label)
        return card

    def create_table(self, headers: list[str], rows: list[list[str]]) -> QTableWidget:
        table = QTableWidget(len(rows), len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        for row_index, row in enumerate(rows):
            for column_index, value in enumerate(row):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row_index, column_index, item)

        table.resizeRowsToContents()
        return table

    def wrap_group(self, title: str, widget: QWidget) -> QGroupBox:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.addWidget(widget)
        return group

    @staticmethod
    def format_money(value: Decimal) -> str:
        return f"¥{value:,.0f}"

    @staticmethod
    def format_pct(value: Decimal) -> str:
        return f"{value * Decimal('100'):.0f}%"


