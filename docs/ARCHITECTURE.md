# 架构说明

项目采用分层结构，目标是让 UI、数据源、策略、撮合、风控、账户和回测彼此解耦。

当前已完成：

- `main.py` 根启动器
- `app/main.py` 应用启动层
- `app/config/settings.py` 配置、路径、交易规则和成本假设
- `app/ui/main_window.py` PySide6 主窗口和 10 个服务接线页面
- `app/ui/background_task.py` Qt 线程池后台行情任务
- `app/data/providers` 统一行情接口、Mock、主备降级和真实公开研究数据源
- `app/database` SQLite 版本迁移和模拟账户事务仓储
- `app/execution` A股规则、成本与模拟撮合
- `app/risk` 单股、总仓位、现金与最大回撤风控
- `app/portfolio` 账户、持仓、订单与成交模型
- `app/strategies` Strategy 基类、四个内置策略和生命周期服务
- `app/backtest` T 日信号、T+1 开盘成交的日线回测骨架
- `app/services/startup.py` 运行目录和依赖探查
- `app/services/trading_app_service.py` UI 与业务内核的应用服务
- `app/utils/logging.py` 滚动日志初始化

关键边界：

- UI 和策略只依赖 `MarketDataProvider`，不直接调用第三方接口。
- 真实行情网络请求由 `QThreadPool` 执行，Qt 主线程只读取线程安全快照。
- 真实源失败时保留最后已验证快照，不使用 Mock 价格冒充真实行情。
- 模拟账户快照在单个 SQLite 事务中保存，写入成功后才提交内存状态。
- 源码模式运行数据位于项目目录；冻结版位于 `%LOCALAPPDATA%/QuantApp`。
- 回测、真实分时和财务披露时点仍是后续扩展边界，详见 `BACKTEST_ASSUMPTIONS.md` 和 `DATA_SOURCES.md`。


