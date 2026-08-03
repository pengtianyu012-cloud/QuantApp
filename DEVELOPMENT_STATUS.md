# DEVELOPMENT_STATUS

更新时间：2026-08-03

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

### 阶段 7：工具链复验与 Windows 实际打包

验收标准：

- pytest、unittest、ruff 和 compileall 全部真实执行通过
- PyInstaller 在当前 Windows 环境真实生成 exe
- 打包后的 exe 可启动，构建失败可正确传播退出码

### 阶段 8：模拟账户数据库持久化与恢复

验收标准：

- 账户、持仓、订单和成交在同一事务中可靠写入 SQLite
- 应用重启后恢复现金、持仓、订单、成交和 T+1 可用数量
- 重复写入与数据库异常有测试覆盖

### 阶段 9：真实免费行情与后台刷新

验收标准：

- 真实数据源通过统一 `MarketDataProvider` 接口接入
- 有超时、重试、退避、限流、缓存、字段校验和失败降级
- 最新价与五档盘口能力经过可选真实网络测试
- Qt 主线程不执行阻塞网络请求

### 阶段 10：本轮完整集成验收

验收标准：

- 完整 pytest、ruff、启动和打包检查通过
- README、数据源文档和本状态文件准确记录能力边界

### 本地机构化改造 Phase 0：交易正确性基线

- 0A：运行模式、可注入时钟与交易日历
- 0B：订单状态机、NEXT_OPEN 与撮合约束
- 0C：净值回撤、成本账务与追加式持久化
- 0D：桌面端集成、迁移文档与完整验收

### 本地机构化改造 Phase 1：本地交易编排与研究真实性

- 1A：收盘信号追加式持久化与订单关联账本
- 1B：收盘信号到下一交易日 NEXT_OPEN 订单编排
- 1C：开盘续撮、取消/过期策略与每日自动对账

## 当前阶段

本地机构化改造 Phase 1B 已完成；当前下一阶段为 Phase 1C 开盘续撮、取消/过期策略与每日自动对账。

## GitHub 仓库连接

- `origin` 已连接到 `https://github.com/pengtianyu012-cloud/QuantApp.git`。
- GitHub 远端原有 `main` 初始提交 `c682300`，仅包含一行 README；已通过 `ours` 合并策略纳入历史，未覆盖本地完整项目文件。
- 本地主分支已由 `master` 重命名为 `main`，并跟踪 `origin/main`。
- 连接合并提交：`6fb5596 chore: connect GitHub repository`。
- 首次非强制推送已成功，本次未要求用户重新登录。

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

- 已实现 Strategy 基类、四个内置策略基础信号逻辑、策略服务和防重复启动。
- 已实现 `DailyBacktestEngine`，严格使用 T 日及之前数据生成信号，T+1 bar 开盘价成交。
- 策略中心、选股结果、历史回测和策略对比页面已完成最小服务接线。
- 阶段 5 提交：`7243a5e feat: add strategy engine and daily backtest`。

### 阶段 6：P2 数据质量、完整文档和 Windows 打包配置

- 已实现 `DataQualityService`，检查 Mock 股票列表、最新行情和五档盘口字段质量。
- 已补充数据质量测试。
- 已创建 `A股量化模拟交易系统.spec`。
- 已更新 `scripts/build_windows.ps1`，使用 spec 并在 PyInstaller 缺失时明确失败。
- 已补充打包配置测试。
- 已更新 README、数据源文档、数据质量文档、用户指南和回测假设文档。

### 阶段 7：工具链复验与 Windows 实际打包

- 已去除 `pyproject.toml` 的 UTF-8 BOM，pytest 9 可正常解析项目配置。
- 已同步依赖范围，当前环境 `pandas 3.0.5`、`pytest 9.1.1` 在声明范围内。
- 已使用 ruff 安全修复与格式化统一项目源码，并将字符串枚举迁移到 Python 3.11 `StrEnum`。
- 已修复 `scripts/build_windows.ps1`：允许覆盖旧产物，并在 PyInstaller 失败时传播错误。
- 已真实生成 `dist/A股量化模拟交易系统/A股量化模拟交易系统.exe`，启动存活检查通过。

### 阶段 8：模拟账户数据库持久化与恢复

- 数据库版本升级到 v2，新增持仓名称和最后买入日期字段，并支持现有 v1 数据库事务迁移。
- 新增 `AccountRepository`，在单个 SQLite 事务中保存账户、持仓、订单和成交完整快照。
- 恢复时保留 Decimal 金额、订单状态、成交成本、T+1 可用数量和带时区时间。
- `TradingAppService` 已在账户副本上执行订单，持久化成功后才提交内存状态；保存失败不会产生伪成交状态。
- 应用启动会恢复 `SIM-001` 本地模拟账户，首次启动自动创建；UI 显示账户存储状态。
- 测试可显式禁用持久化或注入仓储，避免污染用户运行数据库。
- frozen Windows exe 的数据库、日志和配置路径改为 `%LOCALAPPDATA%/QuantApp`，不写入程序安装目录。

### 阶段 9：真实免费行情与后台刷新

- 新增 `AkSharePublicMarketDataProvider`，统一接入交易所股票主表、AkShare 历史接口和腾讯公开网页实时行情。
- 历史人工验收曾实测上交所主板 1698 只、科创板 612 只、深交所 A 股 2892 只，合计 5202 只，不含北交所。
- 真实最新价、涨跌、OHLC、成交量、成交额、换手率、行情时间、买卖五档、内盘和外盘已实测成功。
- 腾讯成交量和盘口量按“手”转换为“股”；委比、委差和精确到股的成交量标记为不支持，不伪造。
- 日线以 AkShare/东方财富为主源，企业代理偶发断连时使用低频 AkShare/新浪备用；交易日历已实测。
- 新增 `RateLimitedHttpClient`：证书校验、系统信任库、超时、有限重试、指数退避、限流和空响应检查。
- 自选股、逐股票原始行情缓存 3 秒；股票主表、日线、交易日历缓存 6 小时。
- `TradingAppService` 增加线程安全行情快照和 `QUANT_APP_DATA_PROVIDER=public` 真实源选择。
- Qt 使用 `QThreadPool/QRunnable` 后台刷新自选股和全市场主表；测试验证网络调用线程不是 Qt 主线程。
- 总览连接状态、行情延迟、实时行情表和市场数据表会随后台结果更新。
- AkShare 软件为 MIT License，但其数据说明仅定位学术研究并提示商业风险；公开网页行情无服务等级承诺，文档已明确。
- 阶段 9 提交：`1290103 feat: add real market data and background refresh`。

### 阶段 10：本轮完整集成验收

- 已复核 README、架构说明和用户指南，移除“尚未接入真实行情、后台线程和账户持久化”的过期描述。
- 首次重新打包发现 frozen 应用缺少 `akshare/file_fold/calendar.json`，异常窗口 traceback 已实际提取并定位。
- PyInstaller spec 现使用标准 `collect_data_files("akshare")` 收集 8 个包数据文件，并新增打包配置回归断言。
- 修正版 Mock 冻结版已出现正常应用窗口，并创建 `%LOCALAPPDATA%/QuantApp` 下的数据库、日志、缓存和配置目录。
- 修正版 public 冻结版连续运行 45 秒，跨过后台行情和低频股票主表任务窗口，仍为正常应用窗口且无异常对话框。
- PyInstaller 告警复核未发现当前 SQLite、Qt、AkShare/腾讯行情调用链的阻断缺失项；其余为跨平台或 pandas/SQLAlchemy 可选后端。

### Phase 0A：运行模式、时钟与交易日历

- 新增 `mock`、`research`、`paper` 三种明确运行模式。
- `research` 和 `paper` 模式注入 `MockMarketDataProvider` 会立即失败，禁止隐式 Mock。
- 策略服务和回测始终使用当前配置的同一个行情 provider，不再在真实模式自动切换 Mock。
- `research` 模式仅允许研究与回测，禁止手工模拟下单；`paper` 才允许真实行情本地模拟交易。
- 新增可注入 `Clock`、`SystemClock`、`FrozenClock` 和 provider 驱动的 `TradingCalendar`。
- Mock 行情当前时间、股票上市资格判断、策略截止日和五年回测区间均由 Clock 推导。
- 修复无历史行情时空回测结果参数缺失导致的 `TypeError`。
- Phase 0A 提交：`27a07e2 feat: define local runtime correctness modes`。

### Phase 0B：订单状态机与撮合正确性

- 建立 CREATED、PENDING_NEXT_OPEN、ELIGIBLE、PARTIALLY_FILLED、FILLED、DEFERRED、CANCELLED、EXPIRED、REJECTED 状态机并拒绝非法转换。
- 订单新增 `eligible_at`、`filled_quantity`、`remaining_quantity` 和 `updated_at`。
- NEXT_OPEN 提交日不会成交，仅在交易日历确认的下一交易日 09:30 后进入撮合。
- 撮合动态检查交易日、连续竞价时段、订单类型、买卖限价、停牌、退市整理、已退市、涨跌停和上市天数。
- 行情年龄改为 `current_time - quote_time` 动态计算，不再信任 provider 的静态延迟字段。
- 部分成交按 remaining quantity 继续撮合，后续成交可准确转为 FILLED。
- 手工订单默认按有价格为 LIMIT、无价格为 MARKET，另支持显式 NEXT_OPEN；新增待处理订单续撮入口。

### Phase 0C：净值回撤、成本账务与追加式持久化

- 新增每日 PortfolioSnapshot，持续保存现金、持仓市值、总资产、净值、历史峰值、当前回撤、最大回撤和累计费用。
- 下单风控强制读取账户真实 current_drawdown；达到 15% 后阻止新增买入，卖出仍允许。
- 滑点和市场冲击统一体现在成交价中，现金仅额外扣除佣金、印花税和过户费，避免价格影响重复扣费。
- Fill 完整记录参考价、成交价、佣金、印花税、过户费、滑点、市场冲击和降级撮合标记。
- OrderEvent 追加记录订单每次状态变化；订单行只更新当前状态，成交和事件只追加，不再删除重建历史流水。
- SQLite 升级到 v3，持久化订单可撮合时间、已成交量、剩余量、费用、账户峰值和回撤；旧 v2 数据可事务升级。
- 旧库迁移会推导历史订单成交/剩余数量、映射旧待成交状态、补种审计事件并去重同一交易日快照。
- ST、退市整理、已退市和上市不足 60 日股票均在撮合层拒绝；停牌订单保持顺延。
- 桌面端股票资格提示使用服务注入的 Clock，不再通过隐式系统日期判断。
- Phase 0C 稳定提交：feat: persist portfolio correctness ledger（见当前分支最近提交）。

### Phase 0D：桌面端集成、迁移文档与完整验收

- 总览新增当前回撤、最大回撤和累计费用，行情延迟按 Clock 当前时间与行情时间动态计算。
- 模拟交易页展示订单类型、已成交量、剩余量、可撮合时间，以及成交参考价和全部成本分项。
- 审计宽表按内容调整列宽并支持横向滚动，避免时间与成本字段被压缩重叠。
- 真实模式界面不再显示 Mock 骨架、Mock 信号或按 Mock 行情估值等误导文案。
- README、架构、交易规则、回测假设、数据源和用户指南已统一 mock/research/paper 行为。
- 新增 v2 到 v3 数据库迁移文档，记录备份、字段/状态映射、成本口径和回退方式。
- 运行代码、文档和测试已移除旧固定演示日期；确定性测试使用显式日期或 FrozenClock，不进入业务逻辑。
- FastAPI、React、Docker、PostgreSQL、Redis 和华为云资源审计均为零命中。
- Phase 0D 稳定提交：docs: complete local correctness phase zero（见当前分支最近提交）。

### Phase 1A：收盘信号追加式持久化与订单关联账本

- SQLite schema 升级到 v4，为信号保存目标仓位、账户、计划交易日、派发状态、关联订单、处理结果和处理时间。
- 新增追加式 SignalRepository；同一账户、策略、股票、方向和信号时点生成稳定 signal_id，重复收盘任务不会重复插入。
- 信号派发状态支持 pending、order_created、skipped 和 rejected，并可在应用重启后恢复。
- Order 新增 signal_id；数据库使用非空唯一索引约束一个信号最多关联一个订单。
- 模拟账户支持注入确定性 order_id 和 signal_id，并在内存层拒绝重复订单或重复信号关联。
- v3 到 v4 迁移保留旧信号和订单数据，补充默认派发状态并在迁移后建立索引。

### Phase 1B：收盘信号到下一交易日 NEXT_OPEN 订单编排

- 新增 CloseSignalOrchestrator，只允许在交易日 15:00 后运行收盘编排，并拒绝跨日、未来时点和错过计划开盘的信号。
- 收盘任务先追加持久化信号，再保存账户及 signal_id 关联订单，最后确认派发状态；账户保存失败时信号保持 pending。
- 应用重启或状态确认中断后，会用账户中已有的 signal_id 订单修复信号状态，不重复创建订单。
- 买入按建议组合目标仓位减去当前持仓和未完成买单预留计算，向下取整到 100 股；预留同时进入单股、总仓位和现金风控。
- 卖出目标按账户总资产计算并允许零股；真实当前回撤达到 15% 时买入被拒绝，卖出仍可创建 NEXT_OPEN 订单。
- research 模式只保存研究信号并标记跳过派单；mock 和 paper 模式才允许创建本地模拟订单。
- TradingAppService 新增收盘策略运行和显式信号派发入口；派发完成后从 SQLite 恢复账户，保证内存与数据库一致。
- README、架构、交易规则、用户指南和 v3 到 v4 迁移说明已同步；桌面自动定时触发、开盘批量续撮和取消/过期明确留到 Phase 1C。

### Python 3.13.2 本机构建基线

- 项目运行版本范围更新为 Python 3.13.2 到 3.13.x，.python-version 固定为 3.13.2。
- Ruff 目标从 py311 更新为 py313；旧式 Generic/TypeVar 缓存类已迁移到 Python 3.13 原生类型参数语法。
- Windows 构建脚本会读取 .venv 的实际解释器版本；不是精确的 3.13.2 时立即停止 PyInstaller 构建。
- README 和打包配置测试已同步，后续开发、测试和 Windows 打包均以本机 Python 3.13.2 为基线。
- 本地稳定提交：a9f406a build: standardize on Python 3.13.2。

## 修改的文件

### Python 3.13.2 本机构建基线

- .python-version
- DEVELOPMENT_STATUS.md
- README.md
- app/data/cache/memory_cache.py
- pyproject.toml
- scripts/build_windows.ps1
- tests/unit/test_packaging_config.py

### Phase 1B

- DEVELOPMENT_STATUS.md
- README.md
- app/risk/checks.py
- app/services/__init__.py
- app/services/close_signal_orchestrator.py
- app/services/trading_app_service.py
- docs/ARCHITECTURE.md
- docs/MIGRATION_PHASE1.md
- docs/TRADING_RULES.md
- docs/USER_GUIDE.md
- tests/unit/test_close_signal_orchestrator.py
- tests/unit/test_risk.py
- tests/unit/test_trading_app_service.py

### Phase 1A

- DEVELOPMENT_STATUS.md
- app/database/__init__.py
- app/database/account_repository.py
- app/database/connection.py
- app/database/schema.py
- app/database/signal_repository.py
- app/models/trading.py
- app/portfolio/account.py
- tests/unit/test_database.py
- tests/unit/test_signal_repository.py

### Phase 0D

- DEVELOPMENT_STATUS.md
- README.md
- app/services/trading_app_service.py
- app/ui/main_window.py
- docs/ARCHITECTURE.md
- docs/BACKTEST_ASSUMPTIONS.md
- docs/DATA_QUALITY.md
- docs/DATA_SOURCES.md
- docs/MIGRATION_PHASE0.md
- docs/TRADING_RULES.md
- docs/USER_GUIDE.md
- tests/integration/test_ui_manual_order.py
- tests/unit/test_account.py
- tests/unit/test_account_repository.py
- tests/unit/test_akshare_public_provider.py
- tests/unit/test_backtest_engine.py
- tests/unit/test_database.py
- tests/unit/test_mock_market_data.py
- tests/unit/test_risk.py
- tests/unit/test_strategies.py
- tests/unit/test_trading_app_service.py
- tests/unit/test_trading_rules.py

### Phase 0C

- app/backtest/engine.py
- app/database/account_repository.py
- app/database/connection.py
- app/database/schema.py
- app/execution/__init__.py
- app/execution/costs.py
- app/execution/simulator.py
- app/models/__init__.py
- app/models/trading.py
- app/portfolio/account.py
- app/risk/checks.py
- app/services/trading_app_service.py
- app/ui/main_window.py
- tests/integration/test_ui_manual_order.py
- tests/unit/test_account.py
- tests/unit/test_account_repository.py
- tests/unit/test_database.py
- tests/unit/test_execution_simulator.py
- tests/unit/test_risk.py
- tests/unit/test_trading_app_service.py
- DEVELOPMENT_STATUS.md

### Phase 0B

- `app/models/trading.py`
- `app/execution/order_state.py`
- `app/execution/simulator.py`
- `app/execution/__init__.py`
- `app/portfolio/account.py`
- `app/services/trading_app_service.py`
- `tests/unit/test_execution_simulator.py`
- `tests/unit/test_trading_app_service.py`
- `tests/unit/test_account_repository.py`
- `tests/integration/test_ui_manual_order.py`
- `DEVELOPMENT_STATUS.md`

### Phase 0A

- `.env.example`
- `app/config/mode.py`
- `app/config/__init__.py`
- `app/utils/clock.py`
- `app/utils/__init__.py`
- `app/execution/calendar.py`
- `app/execution/__init__.py`
- `app/data/providers/base.py`
- `app/data/providers/mock.py`
- `app/services/strategy_service.py`
- `app/services/trading_app_service.py`
- `app/backtest/engine.py`
- `tests/unit/test_runtime_modes.py`
- `DEVELOPMENT_STATUS.md`

### 阶段 9

- `app/data/providers/akshare_public.py`
- `app/data/providers/http_client.py`
- `app/data/providers/__init__.py`
- `app/data/providers/base.py`
- `app/data/cache/memory_cache.py`
- `app/services/trading_app_service.py`
- `app/services/startup.py`
- `app/ui/main_window.py`
- `app/ui/background_task.py`
- `requirements.txt`
- `pyproject.toml`
- `.env.example`
- `tests/unit/test_akshare_public_provider.py`
- `tests/unit/test_http_client.py`
- `tests/unit/test_trading_app_service.py`
- `tests/integration/test_real_market_data.py`
- `tests/integration/test_ui_background_refresh.py`
- `README.md`
- `docs/DATA_SOURCES.md`
- `docs/DATA_QUALITY.md`
- `DEVELOPMENT_STATUS.md`

### 阶段 10

- `A股量化模拟交易系统.spec`
- `tests/unit/test_packaging_config.py`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/USER_GUIDE.md`
- `DEVELOPMENT_STATUS.md`

## 测试结果

Python 3.13.2 本机构建基线更新已执行：

- .\.venv\Scripts\python.exe --version：Python 3.13.2。
- .\.venv\Scripts\python.exe -m pytest：通过，104 个测试通过，2 个真实网络测试默认跳过，2 个子测试通过。
- .\.venv\Scripts\python.exe -m ruff check .：以 py313 目标通过，All checks passed!。
- .\.venv\Scripts\python.exe -m compileall -q app main.py tests：通过。
- .\.venv\Scripts\python.exe -m pip check：通过，No broken requirements found.。
- scripts/build_windows.ps1 PowerShell 语法解析：通过。
- Windows 构建版本门禁：通过，实际解释器为 3.13.2。

Phase 1B 已执行：

- .\.venv\Scripts\python.exe -m pytest：通过，103 个测试通过，2 个真实网络测试默认跳过，2 个子测试通过。
- .\.venv\Scripts\python.exe -m ruff check .：通过，All checks passed!。
- .\.venv\Scripts\python.exe -m ruff format --check Phase 1B Python 文件：通过。
- .\.venv\Scripts\python.exe -m compileall -q app main.py tests：通过。
- PySide6 offscreen 启动：窗口可见，标题正确，10 个页面成功构造。
- 收盘/交易日门禁、目标仓位、未完成买单预留、research 只落账、15% 回撤买卖分流、重复执行、重启对账和写盘失败重试测试：通过。

Phase 1A 已执行：

- .\.venv\Scripts\python.exe -m pytest：通过，91 个测试通过，2 个真实网络测试默认跳过，2 个子测试通过。
- .\.venv\Scripts\python.exe -m ruff check .：通过，All checks passed!。
- .\.venv\Scripts\python.exe -m compileall -q app main.py tests：通过。
- git diff --check：通过；仅提示工作区 LF 将按 Git 配置转换为 CRLF，无空白错误。
- 信号幂等写入、派发状态恢复、signal_id 订单关联恢复和 v3 到 v4 真实旧表迁移测试：通过。

Phase 0D 与 Phase 0 最终验收已执行：

- .\.venv\Scripts\python.exe -m pytest：通过，88 个测试通过，2 个真实网络测试默认跳过，2 个子测试通过。
- .\.venv\Scripts\python.exe -m ruff check .：通过，All checks passed!。
- .\.venv\Scripts\python.exe -m compileall -q app main.py tests：通过。
- git diff --check：通过。
- PySide6 offscreen 启动：窗口可见，10 个页面、12 张指标卡、12 列订单表和 15 列成交表均成功构造。
- 固定日期、隐式真实模式 Mock 文案和禁用云/Web 技术栈审计：通过。

Phase 0C 已执行：

- .\.venv\Scripts\python.exe -m pytest：通过，87 个测试通过，2 个真实网络测试默认跳过，2 个子测试通过。
- .\.venv\Scripts\python.exe -m ruff check .：通过，All checks passed!。
- .\.venv\Scripts\python.exe -m compileall -q app main.py tests：通过。
- 成本只计一次、现金/持仓/费用/总资产对账、日净值峰值与回撤、15% 买入暂停、部分成交恢复和追加式审计测试：通过。
- v2 到 v3 真实旧表结构迁移、旧状态映射、成交量推导、事件补种和同日快照去重测试：通过。
- ST、上市不足 60 日、退市整理、已退市、停牌、涨跌停、T+1 和 100 股规则测试：通过。

Phase 0B 已执行：

- `.\.venv\Scripts\python.exe -m pytest`：通过，81 个测试通过，2 个真实网络测试默认跳过。
- `.\.venv\Scripts\python.exe -m ruff check .`：通过，`All checks passed!`。
- `.\.venv\Scripts\python.exe -m compileall -q main.py app tests`：通过。
- NEXT_OPEN、双向限价、动态行情过期、部分成交续撮、交易日/时段、停牌、涨跌停、退市和终态不可复活测试：通过。

Phase 0A 已执行：

- `.\.venv\Scripts\python.exe -m pytest`：通过，77 个测试通过，2 个真实网络测试默认跳过。
- `.\.venv\Scripts\python.exe -m ruff check .`：通过，`All checks passed!`。
- `.\.venv\Scripts\python.exe -m compileall -q main.py app tests`：通过。
- 生产代码固定日期与隐式 Mock 审计：通过。

阶段 9 已执行：

- `.\.venv\Scripts\python.exe -m pytest`：通过，74 个测试通过，2 个真实网络测试默认跳过。
- `.\.venv\Scripts\python.exe -m ruff check .`：通过，`All checks passed!`。
- `.\.venv\Scripts\python.exe -m compileall -q main.py app tests`：通过。
- `.\.venv\Scripts\python.exe -m unittest discover -s tests`：通过，76 个测试运行，2 个跳过。
- 真实行情、快照服务、后台线程和 UI 定向测试：通过，15 个测试通过。
- `RUN_REAL_MARKET_DATA_TESTS=1` 真实网络测试：通过，2 个测试在 32.45 秒内完成。
- public 模式 offscreen UI：窗口构造 0.1 秒，真实 `600519.SH` 报价后台加载成功；首次验证发现全市场列表 8 秒超时不足，已为低频主表单独调整到 30 秒并由真实套件复验。

阶段 10 已执行：

- `.\.venv\Scripts\python.exe -m pytest`：通过，74 个测试通过，2 个真实网络测试默认跳过。
- `.\.venv\Scripts\python.exe -m unittest discover -s tests`：通过，76 个测试运行，2 个跳过。
- `.\.venv\Scripts\python.exe -m ruff check .`：通过，`All checks passed!`。
- `.\.venv\Scripts\python.exe -m compileall -q main.py app tests`：通过。
- `.\.venv\Scripts\python.exe -m pip check`：通过，`No broken requirements found.`。
- `scripts/test.ps1` 与 `scripts/check.ps1`：通过。
- Mock 源码 offscreen 启动：10 个页面、账户仓储就绪、无持久化错误。
- public 源码 offscreen 启动：10 个页面，构造耗时 0.021 秒，未在 Qt 主线程阻塞网络。
- `RUN_REAL_MARKET_DATA_TESTS=1`：真实网络集成测试 2 个通过，耗时 33.47 秒。
- `scripts/build_windows.ps1`：修复 AkShare 包数据后成功生成 Windows onedir 包。
- Mock 冻结版：正常窗口启动，数据库位于 `%LOCALAPPDATA%/QuantApp/data/quant_app.sqlite3`。
- public 冻结版：后台运行 45 秒保持正常窗口，无未处理异常。

## 当前失败项

- GitHub 推送当前被本机网络阻断：github.com TCP 443、SSH 22 和 ssh.github.com 443 均无法建立 TCP 连接；DNS 与 Ping 正常，尚未进入 GitHub 登录认证阶段。
- 待网络恢复后执行 git push -u origin feat/local-correctness-core；该分支包含 Phase 1A、Phase 1B 和 Python 3.13.2 构建基线提交。
- Phase 1B 无阻断失败项。
- Phase 1C 尚未实现：桌面端不会自动在收盘触发任务，也不会在开盘批量续撮、执行取消/过期策略或生成每日自动对账报告。
- Phase 1A 无阻断失败项。
- 本地机构化改造 Phase 0 无阻断失败项。
- 本轮未重新执行真实网络集成测试；2 个真实网络测试按默认配置跳过，固定响应和 provider 注入测试已通过。
- 本轮未重新执行 PyInstaller 打包；当前源码桌面版 offscreen 启动通过，上一稳定阶段的 Windows 打包曾通过。
- 账户仓储当前基于标准库 `sqlite3` 的显式事务，尚未迁移到 SQLAlchemy ORM；不影响当前 SQLite 持久化能力。
- 回测仍为基础骨架，不含完整卖出、组合再平衡、复权、分红、真实沪深300和财务披露时点控制。
- 真实分时线和可靠历史财务披露时点尚未接入。
- 腾讯公开网页行情不是正式授权行情 API；字段、访问策略和商业许可可能变化，仅用于本地学习研究。
- 真实最新价按行情时间戳计算延迟；休市后会自然超过 30 秒撮合阈值，因此只允许查看，不允许使用旧价成交。

## 下一步准确任务

1. 网络恢复后先执行 git push -u origin feat/local-correctness-core，并确认远端分支包含本地最近提交。
2. 实现 LocalTradingDayScheduler，使用注入 Clock 和 TradingCalendar 保证每个交易日收盘任务最多执行一次，并持久化任务运行状态供重启恢复。
3. 实现开盘批量执行入口：先推进 T+1 可卖数量，再按每个订单的股票读取当日新鲜行情，续撮 PENDING_NEXT_OPEN、DEFERRED 和 PARTIALLY_FILLED 订单。
4. 定义并测试取消与过期策略，并新增每日自动对账报告。
5. 将任务状态和最近执行结果接入 PySide6 桌面诊断/策略页面，网络与批量撮合继续在后台线程运行；稳定后提交 Phase 1C。

## 下一条恢复命令或任务

从 feat/local-correctness-core 执行 git status --short --branch、git log -5 --oneline、.\.venv\Scripts\python.exe --version；确认工作区干净后先执行 git push -u origin feat/local-correctness-core。推送成功后运行 .\.venv\Scripts\python.exe -m pytest，再从 LocalTradingDayScheduler 的任务运行状态持久化和开盘批量续撮入口开始 Phase 1C。
