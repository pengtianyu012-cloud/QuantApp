# DEVELOPMENT_STATUS

更新时间：2026-07-27

## 恢复规则

每次开始工作必须先读取：

- 原始需求附件：`C:\Users\p00855467\.codex\attachments\8839dbed-8eba-4fd0-8526-e1a44e31073b\pasted-text.txt`
- 本文件：`DEVELOPMENT_STATUS.md`
- `git status --short`
- `git log --oneline -5`

如果中断，从“下一步准确任务”继续，禁止推倒重写。

## 总体阶段拆分

### 阶段 0：可恢复开发基线

验收标准：

- 存在 `DEVELOPMENT_STATUS.md`
- Git 仓库可用
- 已提交当前稳定基线
- `.venv`、`.git`、缓存、日志和运行数据不被纳入版本控制

### 阶段 1：P0 工程骨架与核心配置

验收标准：

- 建立 `app/` 分层结构，不再把全部逻辑堆在 UI 文件
- 有统一配置、日志、免责声明、目录常量
- `main.py` 仍可作为桌面端启动入口
- 有基础 README、requirements、pyproject、脚本占位但不伪称完成
- 基础导入测试通过

### 阶段 2：P0 数据库与 Mock 行情

验收标准：

- SQLite 初始化机制可运行
- 建立需求中的核心数据表或等价模型
- 定义 `MarketDataProvider` 抽象接口
- Mock 数据源支持股票列表、最新行情、盘口、日线、交易日历、健康检查
- 数据字段校验、降级状态和无网络测试通过

### 阶段 3：P0 A股交易规则、成本、账户、订单、风控

验收标准：

- A股代码/交易所识别、交易时段、100股规则、T+1、涨跌停、停牌规则可测
- 交易成本集中配置和计算
- 模拟账户、持仓、订单、成交、顺延、撤单可持久化
- 单股30%、总仓位90%、最大回撤15%暂停买入可测

### 阶段 4：P0 桌面端核心页面接线

验收标准：

- 总览、实时行情、市场数据、模拟交易、设置、日志诊断页面具备真实数据绑定或明确“尚未实现”标注
- UI 不在主线程做阻塞网络请求
- 手工模拟买卖有二次确认和免责声明
- 无界面启动测试通过

### 阶段 5：P1 策略引擎、示例策略和回测

验收标准：

- Strategy 基类和四个内置策略可运行
- 实时策略生命周期可控，禁止重复启动
- 日线回测严格 T 日信号、T+1 开盘成交
- 绩效指标和沪深300基准接口具备 Mock/可选真实数据测试

### 阶段 6：P2 文档、数据质量、低估值扩展和打包配置

验收标准：

- README 和 docs 完整说明能力边界
- PyInstaller spec 与 Windows 脚本可检查
- ruff、pytest、启动检查、打包配置检查均有报告

## 当前阶段

阶段 5：P1 策略引擎、示例策略和回测已完成。当前进入阶段 6：P2 数据质量、完整文档和 Windows 打包配置。

## 已完成内容

### 阶段 0：可恢复开发基线

- 已正确以 UTF-8 读取原始需求附件。
- 已初始化 Git 仓库。
- 已创建 `.gitignore` 和 `DEVELOPMENT_STATUS.md`。
- 阶段 0 提交：`24ba712 chore: establish resumable development baseline`。
- 阶段 0 状态同步提交：`eb4a841 docs: record baseline completion`。

### 阶段 1：P0 工程骨架与核心配置

- 已建立 `app/` 分层结构。
- 已将根目录 `main.py` 改为薄启动器，真实启动逻辑迁移到 `app/main.py`。
- 已将 PySide6 主窗口迁移到 `app/ui/main_window.py`，并扩展为 10 个核心页面。
- 阶段 1 提交：`e6201b6 feat: scaffold application architecture`。

### 阶段 2：P0 数据库与 Mock 行情

- 已实现 SQLite 初始化机制、版本记录和需求中的 19 张核心表。
- 已定义 `MarketDataProvider` 抽象接口和行情数据模型。
- 已实现 Mock 行情、主备降级、TTL 缓存和行情字段校验。
- 阶段 2 提交：`f400429 feat: add database and mock market data`。

### 阶段 3：P0 A股交易规则、成本、账户、订单、风控

- 已实现 A股代码与交易所识别、交易时段、100股、T+1、涨跌停和新股规则不确定处理。
- 已实现集中交易成本计算、模拟账户、风控和撮合可成交性判断。
- 阶段 3 提交：`7de260d feat: implement simulated trading core`。

### 阶段 4：P0 桌面端核心页面接线

- 已创建 `TradingAppService`，组合 Mock 行情、模拟账户、风控和撮合内核。
- 总览、实时行情、市场数据、模拟交易页面已接入 Mock 和账户内核。
- 手工模拟买入/卖出已接入服务层，并保留二次确认和免责声明。
- 阶段 4 提交：`a4dfa31 feat: wire desktop pages to simulated trading service`。

### 阶段 5：P1 策略引擎、示例策略和回测

- 已实现 Strategy 基类、策略状态、信号方向和完整信号记录字段。
- 已实现四个内置策略基础信号逻辑：均线趋势、动量选股、低估值因子、盘口与量价演示。
- 已实现 `StrategyService`，支持启动、暂停、停止、状态查询和防重复启动。
- 已实现 Mock 日线策略信号生成和盘口演示策略信号生成。
- 已实现 `DailyBacktestEngine`，严格使用 T 日及之前数据生成信号，T+1 bar 开盘价成交。
- 策略中心、选股结果、历史回测和策略对比页面已完成最小服务接线。
- 已更新 README、用户指南和回测假设文档。

## 修改的文件

- `app/strategies/base.py`
- `app/strategies/builtin.py`
- `app/strategies/__init__.py`
- `app/services/strategy_service.py`
- `app/services/trading_app_service.py`
- `app/services/__init__.py`
- `app/backtest/engine.py`
- `app/backtest/__init__.py`
- `app/ui/main_window.py`
- `README.md`
- `docs/USER_GUIDE.md`
- `docs/BACKTEST_ASSUMPTIONS.md`
- `tests/unit/test_strategies.py`
- `tests/unit/test_strategy_service.py`
- `tests/unit/test_backtest_engine.py`
- `tests/integration/test_ui_strategy_preview.py`
- `DEVELOPMENT_STATUS.md`

## 测试结果

阶段 5 已执行：

- `.\.venv\Scripts\python.exe -m compileall -q main.py app tests`：通过。
- `.\.venv\Scripts\python.exe -m unittest discover -s tests`：通过，55 个测试 OK。
- `.\.venv\Scripts\python.exe -c "from app.main import build_application; app, window = build_application(['test']); print(window.windowTitle(), window.tabs.count()); window.close(); app.processEvents()"`：通过，输出 `A股量化模拟交易系统 10`。
- `.\scripts\test.ps1`：通过，55 个测试 OK。
- `.\scripts\check.ps1`：通过编译检查；ruff 未安装，脚本明确提示跳过 ruff。

## 当前失败项

- 当前虚拟环境仅确认 PySide6 已安装；`pandas`、`numpy`、`SQLAlchemy`、`pytest`、`ruff`、`PyInstaller` 尚未安装。
- 数据库当前使用标准库 `sqlite3` 完成可运行初始化；尚未切换到 SQLAlchemy ORM。
- 尚未接入真实免费行情数据源，真实最新价和真实五档盘口未验证。
- UI 目前使用同步 Mock 数据读取，尚未实现后台 QThread/线程池刷新。
- 订单、成交和账户状态尚未持久化写入数据库，应用重启后不会恢复账户。
- 回测当前为基础骨架，不含完整卖出规则、组合再平衡、复权、分红、真实沪深300基准和真实财务披露时点控制。
- 尚未执行真实 ruff 检查，因为 ruff 未安装。
- 尚未完成 Windows 实际打包或 PyInstaller spec 验证。

## 下一步准确任务

1. 开始阶段 6：实现数据质量报告模型/服务，补充 Mock 数据质量检查。
2. 完善 README 和 docs，明确真实数据源未接入、Mock 字段支持范围、交易/回测限制和启动命令。
3. 补充 PyInstaller spec 或强化 `scripts/build_windows.ps1`，明确 Windows 打包边界。
4. 如允许安装依赖，尝试安装 requirements 并执行真实 pytest/ruff；否则继续保留当前缺失项记录。
5. 运行编译检查、unittest、启动检查，更新 `DEVELOPMENT_STATUS.md` 并提交阶段 6 稳定结果。

## 下一条恢复命令或任务

从项目根目录执行：读取原始需求、读取 `DEVELOPMENT_STATUS.md`、查看 `git status --short` 和 `git log --oneline -5`，然后继续“阶段 6：P2 数据质量、完整文档和 Windows 打包配置”。优先任务是创建 `app/services/data_quality_service.py`、更新 docs，并补充打包配置检查。
