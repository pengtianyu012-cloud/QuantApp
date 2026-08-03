# A股量化模拟交易系统

这是一个面向 Windows 10/11 的桌面端 A股量化模拟交易系统。项目当前处于学习与开发同步阶段，第一目标是建立可运行、可测试、可恢复开发的本地模拟交易软件。

重要免责声明：本软件仅用于量化研究和模拟交易，不构成投资建议，不连接真实券商，不执行真实订单。

## 当前状态

- 已完成 PySide6 桌面端启动骨架。
- 已建立 `app/` 分层结构、配置模块、日志模块和 10 个核心页面骨架。
- 已实现 Mock 行情和真实 `AkSharePublicMarketDataProvider`；真实最新价、五档盘口、全市场股票列表、日线和交易日历已实测。
- 已实现 SQLite v4 账户与信号持久化、订单状态审计、每日净值快照、真实回撤风控、完整交易成本、部分成交续撮、收盘信号到 NEXT_OPEN 订单编排、基础策略引擎和日线回测骨架；10 个页面已接入服务层。
- 未实现功能会在界面中标注“尚未实现”。

## 技术栈

- Python 3.11
- PySide6
- pandas、numpy、SQLAlchemy、AkShare、requests、truststore
- SQLite：账户、持仓、订单、成交和运行数据持久化
- unittest、pytest、ruff
- PyInstaller：Windows 已实际打包验证

## 目录结构

```text
app/                 应用源码
app/config/          配置、路径、交易规则和成本假设
app/ui/              PySide6 主窗口、页面和样式
app/models/          业务元数据模型
app/services/        启动和应用服务
app/utils/           日志等工具
tests/               单元测试与集成测试
docs/                架构、数据源和用户文档
scripts/             Windows PowerShell 开发脚本
data/                本地运行数据目录，不提交数据库
logs/                本地日志目录，不提交日志
main.py              根启动入口
```

## 启动

```powershell
.\.venv\Scripts\python.exe main.py
```

也可以使用：

```powershell
.\scripts\run_dev.ps1
```

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check .
```

或：

```powershell
.\scripts\test.ps1
```

## 静态检查

```powershell
.\scripts\check.ps1
```

如果 ruff 未安装，脚本会跳过 ruff 并提示安装依赖。

## 安装依赖

安装或同步全部运行、测试与打包依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 数据源说明

当前已完成统一 MarketDataProvider、Mock 源和真实公开研究数据源。真实源使用 AkShare/交易所主表、腾讯按股票批量实时行情、AkShare 日线和交易日历。运行模式必须显式区分：

- mock：离线开发与测试，可以执行本地模拟订单。
- research：真实公开研究行情，只允许研究、策略和回测，禁止手工下单。
- paper：真实公开研究行情，可以执行仅写入本地账户的模拟订单。

默认模式为 mock。启用真实研究模式：

```powershell
$env:QUANT_APP_MODE = "research"
.\.venv\Scripts\python.exe main.py
```

需要用真实公开行情执行本地模拟盘时，将模式设为 paper。research 和 paper 禁止注入或隐式回退 MockMarketDataProvider；真实源失败时显示异常并停止使用过期行情。

真实行情在 Qt 线程池中刷新，自选股默认每 3 秒一次，全市场主表使用长缓存。委比、委差、真实分时线和可靠历史财务披露时点当前不支持，界面不会伪造。详细字段和许可边界见 docs/DATA_SOURCES.md。

五档盘口中的买量/卖量表示委托量，不等同于实际成交量。内盘/外盘属于主动卖出/主动买入成交口径，必须由数据源明确支持后才展示。

## 策略与回测

当前已实现 Strategy 基类、内置策略基础信号逻辑、策略服务防重复启动，以及 T 日收盘信号/T+1 开盘成交的日线回测骨架。策略和回测始终使用当前模式配置的同一个行情 provider；真实模式不会切换到 Mock。回测默认区间由注入 Clock 推导最近 5 年，不代表真实投资能力。

服务层可在交易日 15:00 后把收盘信号追加写入 SQLite，并按建议目标仓位、当前持仓和未完成买单预留生成下一交易日 09:30 可撮合的 NEXT_OPEN 模拟订单。signal_id 与 order_id 稳定关联，重复执行和应用重启不会重复下单。research 模式只保存研究信号，不创建订单；桌面自动定时触发和开盘批量续撮仍属于后续阶段。

## 模拟交易规则

- 初始资金：100,000 元
- 单股仓位上限：30%
- 总仓位上限：90%
- 最大回撤达到 15% 暂停新增买入
- 普通A股买入数量为 100 股整数倍
- 支持 T+1 规则
- 停牌、涨跌停无法成交时订单顺延
- NEXT_OPEN 订单最早在下一交易日开盘后成交
- 部分成交会保存已成交量和剩余量并继续撮合
- 佣金、印花税、过户费、滑点和市场冲击均写入成交审计
- 每日净值、历史峰值、当前回撤和最大回撤可在重启后恢复

以上规则当前已进入配置模块、可测试内核和桌面端模拟交易页。手工模拟买入/卖出会先二次确认，并且只在软件内部生成模拟订单。

## 数据库迁移

应用启动时会在单个 SQLite 事务中按版本顺序升级到 v4，不删除既有订单、成交或信号。v2→v3 的订单/账务迁移见 docs/MIGRATION_PHASE0.md，v3→v4 的信号派发账本迁移见 docs/MIGRATION_PHASE1.md。升级前建议备份本地数据库。

## Windows 打包

```powershell
.\scripts\build_windows.ps1
```

已在 Windows 11 / PyInstaller 6.21.0 实际生成并启动检查 `dist/A股量化模拟交易系统/A股量化模拟交易系统.exe`。打包应用的数据库和日志写入 `%LOCALAPPDATA%\QuantApp`，不写入程序目录。






