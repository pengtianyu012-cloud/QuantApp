# 架构说明

项目采用分层结构，目标是让 UI、数据源、策略、撮合、风控、账户和回测彼此解耦。

当前已完成：

- `main.py` 根启动器
- `app/main.py` 应用启动层
- `app/config/settings.py` 配置、路径、交易规则和成本假设
- `app/ui/main_window.py` PySide6 主窗口和 10 个页面骨架
- `app/models/strategy.py` 内置策略目录
- `app/services/startup.py` 运行目录和依赖探查
- `app/utils/logging.py` 滚动日志初始化

后续阶段将补充：

- `app/data/providers` 行情数据源接口、Mock适配器和主备降级包装器
- `app/database` SQLite 初始化、版本记录和核心表结构
- `app/engine` 事件驱动交易引擎
- `app/execution` 模拟撮合
- `app/risk` 风控
- `app/portfolio` 账户、持仓和资产快照
- `app/strategies` Strategy 基类和四个内置策略
- `app/backtest` 历史回测与绩效分析

