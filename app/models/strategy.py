from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyInfo:
    name: str
    description: str
    signal_rule: str
    risk_note: str
    stage: str
    status: str = "尚未实现"


def built_in_strategy_catalog() -> list[StrategyInfo]:
    """返回内置策略目录，具体策略逻辑在后续阶段接入。"""

    return [
        StrategyInfo(
            name="均线趋势",
            description="用短期均线和长期均线的相对位置识别趋势方向。",
            signal_rule="收盘后计算短长周期均线，多头排列且成交量达标时进入候选池。",
            risk_note="趋势反转、止损或回撤扩大时降低仓位。",
            stage="P1",
        ),
        StrategyInfo(
            name="动量选股",
            description="比较可配置回看周期内的收益和流动性，优先选择相对强势股票。",
            signal_rule="剔除停牌、ST、退市整理、新股后按动量得分排序。",
            risk_note="追高和涨停无法成交风险较高，订单需支持顺延。",
            stage="P1",
        ),
        StrategyInfo(
            name="低估值因子",
            description="基于PE、PB、ROE等指标寻找相对低估且质量尚可的股票。",
            signal_rule="仅在财务披露时间可靠时参与回测信号。",
            risk_note="若数据源缺少历史披露时点，必须显示未来函数风险警告。",
            stage="P2",
        ),
        StrategyInfo(
            name="盘口与量价演示",
            description="用于验证实时行情、盘口和撮合链路的演示策略。",
            signal_rule="基于买卖盘不平衡、价格变化和成交量变化生成演示信号。",
            risk_note="仅用于模拟模式验证，不代表具备盈利能力。",
            stage="P1",
        ),
    ]
