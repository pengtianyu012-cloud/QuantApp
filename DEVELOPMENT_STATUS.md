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

阶段 3：P0 A股交易规则、成本、账户、订单、风控已完成。当前进入阶段 4：P0 桌面端核心页面接线。

## 已完成内容

### 阶段 0：可恢复开发基线

- 已正确以 UTF-8 读取原始需求附件。
- 已初始化 Git 仓库。
- 已创建 `.gitignore`，避免提交 `.venv`、缓存、日志、运行数据库和本地密钥。
- 已创建 `DEVELOPMENT_STATUS.md` 并提交可恢复基线。
- 阶段 0 提交：`24ba712 chore: establish resumable development baseline`。
- 阶段 0 状态同步提交：`eb4a841 docs: record baseline completion`。

### 阶段 1：P0 工程骨架与核心配置

- 已建立 `app/` 分层结构。
- 已将根目录 `main.py` 改为薄启动器，真实启动逻辑迁移到 `app/main.py`。
- 已将 PySide6 主窗口迁移到 `app/ui/main_window.py`，并扩展为 10 个核心页面。
- 已集中配置交易规则、成本假设、刷新参数、运行路径和免责声明。
- 阶段 1 提交：`e6201b6 feat: scaffold application architecture`。

### 阶段 2：P0 数据库与 Mock 行情

- 已实现 SQLite 初始化机制、版本记录和需求中的 19 张核心表。
- 已定义 `MarketDataProvider` 抽象接口和行情数据模型。
- 已实现 `MockMarketDataProvider`，支持股票列表、最新行情、五档盘口、分时、日线、交易日历、财务指标示例和健康检查。
- 已实现主备降级、TTL 缓存和行情字段校验。
- 阶段 2 提交：`f400429 feat: add database and mock market data`。

### 阶段 3：P0 A股交易规则、成本、账户、订单、风控

- 已实现 A股代码与交易所识别，支持主板、创业板、科创板识别。
- 已实现交易时段判断，使用 `Asia/Shanghai` 或命名 UTC+8 回退，不依赖 Windows 本地时区。
- 已实现 100 股整数倍买入规则、零股尾仓卖出规则和 T+1 规则。
- 已实现主板 10%、创业板/科创板 20%、ST 5% 涨跌停规则。
- 上市不足 60 日股票标记为“规则不确定”，禁止强制模拟成交。
- 已实现集中交易成本计算：佣金、最低佣金、印花税、过户费、滑点、市场冲击和成交量参与率。
- 已实现模拟账户内核：现金、持仓、可卖数量、订单提交、成交应用和资产计算。
- 已实现风控：单股30%、总仓位90%、最大回撤15%暂停新增买入、卖出豁免和现金不足拦截。
- 已实现撮合可成交性判断：停牌、行情过期、涨停无法买入、跌停无法卖出、订单顺延、部分成交、无盘口降级撮合。
- 已更新 README、架构文档、交易规则文档和模拟交易页文案。

## 修改的文件

- `app/models/trading.py`
- `app/models/__init__.py`
- `app/execution/trading_rules.py`
- `app/execution/costs.py`
- `app/execution/simulator.py`
- `app/execution/__init__.py`
- `app/portfolio/account.py`
- `app/portfolio/__init__.py`
- `app/risk/checks.py`
- `app/risk/__init__.py`
- `app/ui/main_window.py`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/TRADING_RULES.md`
- `tests/unit/test_trading_rules.py`
- `tests/unit/test_trade_costs.py`
- `tests/unit/test_account.py`
- `tests/unit/test_risk.py`
- `tests/unit/test_execution_simulator.py`
- `DEVELOPMENT_STATUS.md`

## 测试结果

阶段 3 已执行：

- `.\.venv\Scripts\python.exe -m compileall -q main.py app tests`：通过。
- `.\.venv\Scripts\python.exe -m unittest discover -s tests`：通过，42 个测试 OK。
- `.\.venv\Scripts\python.exe -c "from app.main import build_application; app, window = build_application(['test']); print(window.windowTitle(), window.tabs.count()); window.close(); app.processEvents()"`：通过，输出 `A股量化模拟交易系统 10`。
- `.\scripts\test.ps1`：通过，42 个测试 OK。
- `.\scripts\check.ps1`：通过编译检查；ruff 未安装，脚本明确提示跳过 ruff。

## 当前失败项

- 当前虚拟环境仅确认 PySide6 已安装；`pandas`、`numpy`、`SQLAlchemy`、`pytest`、`ruff`、`PyInstaller` 尚未安装。
- 数据库当前使用标准库 `sqlite3` 完成可运行初始化；尚未切换到 SQLAlchemy ORM。
- 尚未接入真实免费行情数据源，真实最新价和真实五档盘口未验证。
- Mock 行情、账户、风控和撮合内核尚未绑定到 UI 页面。
- 订单、成交和账户状态尚未持久化写入数据库。
- 尚未实现策略引擎、回测、绩效分析和 Windows 实际打包。
- 尚未执行真实 ruff 检查，因为 ruff 未安装。

## 下一步准确任务

1. 开始阶段 4：将 Mock 行情绑定到总览、实时行情和市场数据页面。
2. 将模拟账户、持仓、待成交订单、成交记录绑定到模拟交易页面。
3. 实现手工模拟买入/卖出表单，保留二次确认和“不会发送到券商”提示。
4. 将风控状态、成本假设和未实现能力状态显示在 UI 中。
5. 增加 UI 最小交互测试或服务层测试，确保下单后账户和表格状态变化正确。
6. 运行编译检查、unittest、启动检查，更新 `DEVELOPMENT_STATUS.md` 并提交阶段 4 稳定结果。

## 下一条恢复命令或任务

从项目根目录执行：读取原始需求、读取 `DEVELOPMENT_STATUS.md`、查看 `git status --short` 和 `git log --oneline -5`，然后继续“阶段 4：P0 桌面端核心页面接线”。优先任务是重构 `app/ui/main_window.py`，让页面从 `MockMarketDataProvider`、`SimulatedAccount`、`RiskManager` 和 `SimulatedMatcher` 读取真实内核状态。
