import sys
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QProgressBar,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class TradingRules:
    """A股模拟交易的核心约束。"""

    initial_cash: int = 100_000
    max_single_position_pct: float = 0.30
    max_drawdown_pct: float = 0.15
    min_listing_days: int = 60
    backtest_years: int = 5
    benchmark: str = "沪深300"
    signal_time: str = "每日收盘后"
    execution_time: str = "下一交易日开盘"


@dataclass(frozen=True)
class StrategyInfo:
    name: str
    description: str
    signal_rule: str
    risk_note: str


class QuantMainWindow(QMainWindow):
    """量化模拟交易软件主窗口。"""

    def __init__(self) -> None:
        super().__init__()

        self.rules = TradingRules()
        self.strategies = [
            StrategyInfo(
                "均线趋势",
                "用短期均线和长期均线的相对位置识别趋势方向。",
                "收盘后计算 MA20/MA60，多头排列时进入候选池。",
                "趋势反转或回撤扩大时降低仓位。",
            ),
            StrategyInfo(
                "动量选股",
                "比较近 20/60 个交易日涨幅，优先选择相对强势股票。",
                "剔除停牌、ST、退市整理、新股后按动量得分排序。",
                "避免单日涨停无法成交，订单自动进入重试队列。",
            ),
            StrategyInfo(
                "低估值因子",
                "基于 PE、PB 等估值指标寻找相对低估股票。",
                "估值分位较低且流动性达标时生成买入信号。",
                "估值修复慢，需搭配最大回撤和仓位限制。",
            ),
        ]

        self.setWindowTitle("A股量化模拟交易系统")
        self.resize(1200, 760)
        self.setMinimumSize(900, 600)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.create_market_data_page(), "市场数据")
        self.tabs.addTab(self.create_strategy_page(), "策略中心")
        self.tabs.addTab(self.create_selection_page(), "选股结果")
        self.tabs.addTab(self.create_backtest_page(), "回测分析")
        self.tabs.addTab(self.create_trading_page(), "模拟交易")
        self.tabs.addTab(self.create_compare_page(), "策略对比")
        self.setCentralWidget(self.tabs)

        status_bar = QStatusBar()
        status_bar.showMessage(
            f"系统就绪 | 模拟资金：¥{self.rules.initial_cash:,.0f} | "
            f"单股上限：{self.rules.max_single_position_pct:.0%} | "
            f"最大回撤暂停：{self.rules.max_drawdown_pct:.0%}"
        )
        self.setStatusBar(status_bar)

    def create_market_data_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(
            self.create_rule_summary(
                [
                    ("股票池", "沪深 A 股全覆盖"),
                    ("排除规则", f"ST / 退市整理 / 上市不足 {self.rules.min_listing_days} 日"),
                    ("信号时间", self.rules.signal_time),
                    ("成交时间", self.rules.execution_time),
                ]
            )
        )

        table = self.create_table(
            ["代码", "名称", "市场", "上市天数", "交易状态", "是否纳入", "说明"],
            [
                ["600519", "贵州茅台", "沪市主板", "8000+", "正常", "是", "满足基础股票池条件"],
                ["000001", "平安银行", "深市主板", "8000+", "正常", "是", "满足基础股票池条件"],
                ["300750", "宁德时代", "创业板", "2000+", "正常", "是", "满足基础股票池条件"],
                ["688001", "华兴源创", "科创板", "2500+", "正常", "是", "满足基础股票池条件"],
                ["000000", "示例ST股", "深市主板", "1200", "ST", "否", "触发 ST 排除规则"],
                ["301999", "示例新股", "创业板", "32", "正常", "否", "上市不足 60 日"],
            ],
        )
        layout.addWidget(self.wrap_group("股票池过滤预览", table))
        return page

    def create_strategy_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        selector_row = QHBoxLayout()
        selector_label = QLabel("当前策略")
        selector_label.setObjectName("fieldLabel")
        selector = QComboBox()
        selector.addItems([strategy.name for strategy in self.strategies])
        selector.setMinimumWidth(220)
        run_button = QPushButton("生成收盘信号")
        run_button.clicked.connect(self.generate_signal_preview)
        selector_row.addWidget(selector_label)
        selector_row.addWidget(selector)
        selector_row.addStretch()
        selector_row.addWidget(run_button)
        layout.addLayout(selector_row)

        table = self.create_table(
            ["策略", "核心逻辑", "信号生成", "风控关注"],
            [
                [
                    strategy.name,
                    strategy.description,
                    strategy.signal_rule,
                    strategy.risk_note,
                ]
                for strategy in self.strategies
            ],
        )
        layout.addWidget(self.wrap_group("内置策略库", table))

        notes = QTextEdit()
        notes.setReadOnly(True)
        notes.setMinimumHeight(130)
        notes.setText(
            "开发记录\n"
            "1. 先保持三类策略的统一输入输出：股票池、行情序列、财务因子、风险状态。\n"
            "2. 每日收盘后只生成信号，不在收盘价成交。\n"
            "3. 下一交易日开盘若停牌或涨跌停无法成交，订单进入重试队列。\n"
            "4. 回撤达到 15% 后暂停新增交易，只允许已有重试订单继续按规则处理。"
        )
        layout.addWidget(self.wrap_group("学习与开发同步记录", notes))
        return page

    def create_selection_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(
            self.create_rule_summary(
                [
                    ("候选来源", "收盘后策略评分"),
                    ("仓位约束", f"单股不超过 {self.rules.max_single_position_pct:.0%}"),
                    ("买入预算", "以账户权益和现有持仓动态计算"),
                    ("无法成交", "下一交易日继续重试"),
                ]
            )
        )

        self.selection_table = self.create_table(
            ["排名", "代码", "名称", "策略", "得分", "建议动作", "目标仓位", "执行日"],
            [
                ["1", "600519", "贵州茅台", "低估值因子", "86.4", "买入", "20%", "下一交易日开盘"],
                ["2", "300750", "宁德时代", "动量选股", "82.1", "买入", "18%", "下一交易日开盘"],
                ["3", "000001", "平安银行", "均线趋势", "78.5", "观察", "0%", "等待确认"],
            ],
        )
        layout.addWidget(self.wrap_group("今日信号预览", self.selection_table))
        return page

    def create_backtest_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        metrics = QGridLayout()
        metrics.setSpacing(12)
        cards = [
            ("回测周期", f"最近 {self.rules.backtest_years} 年", "滚动使用历史交易日"),
            ("基准指数", self.rules.benchmark, "用于超额收益比较"),
            ("初始资金", f"¥{self.rules.initial_cash:,.0f}", "本地模拟账户"),
            ("最大回撤阈值", f"{self.rules.max_drawdown_pct:.0%}", "触发后暂停交易"),
        ]
        for index, (title, value, detail) in enumerate(cards):
            metrics.addWidget(self.create_metric_card(title, value, detail), index // 2, index % 2)
        layout.addLayout(metrics)

        progress = QProgressBar()
        progress.setRange(0, 15)
        progress.setValue(0)
        progress.setFormat("当前回撤 0.0% / 暂停阈值 15.0%")
        layout.addWidget(self.wrap_group("回撤监控", progress))

        table = self.create_table(
            ["策略", "年化收益", "最大回撤", "夏普比率", "胜率", "相对沪深300"],
            [
                ["均线趋势", "待回测", "待回测", "待回测", "待回测", "待回测"],
                ["动量选股", "待回测", "待回测", "待回测", "待回测", "待回测"],
                ["低估值因子", "待回测", "待回测", "待回测", "待回测", "待回测"],
            ],
        )
        layout.addWidget(self.wrap_group("回测结果占位表", table))
        return page

    def create_trading_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        metrics = QGridLayout()
        metrics.setSpacing(12)
        cards = [
            ("总资产", f"¥{self.rules.initial_cash:,.0f}", "初始模拟资金"),
            ("可用现金", f"¥{self.rules.initial_cash:,.0f}", "尚未建仓"),
            ("持仓市值", "¥0", "当前无持仓"),
            ("交易状态", "允许交易", "回撤未触发暂停"),
        ]
        for index, (title, value, detail) in enumerate(cards):
            metrics.addWidget(self.create_metric_card(title, value, detail), index // 4, index % 4)
        layout.addLayout(metrics)

        positions = self.create_table(
            ["代码", "名称", "数量", "成本价", "最新价", "持仓占比", "浮动盈亏"],
            [["-", "-", "0", "-", "-", "0%", "¥0"]],
        )
        layout.addWidget(self.wrap_group("当前持仓", positions))

        retries = self.create_table(
            ["订单号", "代码", "名称", "方向", "目标金额", "未成交原因", "下次处理"],
            [
                ["R-0001", "示例", "停牌股票", "买入", "¥30,000", "停牌", "下一交易日开盘重试"],
                ["R-0002", "示例", "涨停股票", "买入", "¥18,000", "涨停无法买入", "下一交易日开盘重试"],
            ],
        )
        layout.addWidget(self.wrap_group("未成交重试队列", retries))
        return page

    def create_compare_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        layout.addWidget(
            self.create_rule_summary(
                [
                    ("比较对象", "三种内置策略"),
                    ("统一基准", self.rules.benchmark),
                    ("统一资金", f"¥{self.rules.initial_cash:,.0f}"),
                    ("统一风控", "单股 30% / 回撤 15% 暂停"),
                ]
            )
        )

        table = self.create_table(
            ["策略", "适用市场", "换手特征", "主要风险", "下一步开发"],
            [
                ["均线趋势", "趋势明显阶段", "中", "震荡市反复止损", "接入 MA 参数和信号回测"],
                ["动量选股", "强者恒强阶段", "高", "追高和涨停无法成交", "接入动量窗口与成交约束"],
                ["低估值因子", "价值修复阶段", "低", "低估值陷阱", "接入财务因子和分位计算"],
            ],
        )
        layout.addWidget(self.wrap_group("策略横向比较", table))
        return page

    def generate_signal_preview(self) -> None:
        self.statusBar().showMessage(
            "已生成收盘信号预览 | 实盘模拟成交将在下一交易日开盘处理"
        )
        if hasattr(self, "selection_table"):
            self.selection_table.selectRow(0)

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


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(
        """
        QWidget {
            color: #202124;
            font-family: "Microsoft YaHei";
            font-size: 14px;
        }

        QMainWindow,
        QTabWidget::pane {
            background: #f5f7fb;
        }

        QTabBar::tab {
            min-width: 112px;
            padding: 10px 14px;
        }

        QTabBar::tab:selected {
            background: #ffffff;
            font-weight: 600;
        }

        QGroupBox {
            background: #ffffff;
            border: 1px solid #dfe3eb;
            border-radius: 6px;
            font-weight: 600;
            margin-top: 12px;
            padding-top: 16px;
        }

        QGroupBox::title {
            left: 12px;
            padding: 0 4px;
        }

        QFrame#metricCard {
            background: #ffffff;
            border: 1px solid #dfe3eb;
            border-radius: 6px;
        }

        QLabel#metricTitle,
        QLabel#summaryLabel {
            color: #5f6368;
            font-size: 13px;
            font-weight: 500;
        }

        QLabel#metricValue {
            color: #0f172a;
            font-size: 22px;
            font-weight: 700;
        }

        QLabel#metricDetail,
        QLabel#summaryValue {
            color: #3c4043;
            font-weight: 400;
        }

        QLabel#fieldLabel {
            font-weight: 600;
        }

        QPushButton {
            background: #1f6feb;
            border: 0;
            border-radius: 5px;
            color: #ffffff;
            font-weight: 600;
            padding: 8px 14px;
        }

        QPushButton:hover {
            background: #1557ba;
        }

        QTableWidget {
            background: #ffffff;
            gridline-color: #edf0f5;
            selection-background-color: #dbeafe;
            selection-color: #0f172a;
        }

        QHeaderView::section {
            background: #eef2f7;
            border: 0;
            border-right: 1px solid #dfe3eb;
            color: #202124;
            font-weight: 600;
            padding: 8px;
        }
        """
    )

    window = QuantMainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
