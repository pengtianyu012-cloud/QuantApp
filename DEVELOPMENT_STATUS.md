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

## 当前阶段

阶段 7 已完成并提交前待记录；下一阶段为阶段 8 模拟账户数据库持久化与恢复。

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

## 修改的文件

- `pyproject.toml`
- `requirements.txt`
- `scripts/build_windows.ps1`
- `app/**/*.py`（ruff 安全修复、格式化及 `StrEnum` 更新）
- `tests/**/*.py`（ruff 格式化，不改变测试语义）
- `DEVELOPMENT_STATUS.md`

## 测试结果

阶段 7 已执行：

- `.\.venv\Scripts\python.exe -m pytest`：通过，59 个测试通过。
- `.\.venv\Scripts\python.exe -m unittest discover -s tests`：通过，59 个测试 OK。
- `.\.venv\Scripts\python.exe -m ruff check .`：通过，`All checks passed!`。
- `.\.venv\Scripts\python.exe -m compileall -q main.py app tests`：通过。
- 源码无界面启动检查：通过，输出 `A股量化模拟交易系统 10`。
- `.\scripts\build_windows.ps1`：通过，PyInstaller 6.21.0 在 Windows 11 / Python 3.13.2 下真实生成 exe。
- 打包 exe 启动存活 5 秒检查：通过，随后由测试进程主动关闭。

## 当前失败项

- 当前虚拟环境是 Python 3.13.2；项目仍以 Python 3.11 为最低版本和 ruff 目标，但尚未在 Python 3.11 环境复验。
- 数据库当前使用标准库 `sqlite3` 初始化；订单、成交、账户和持仓尚未写入数据库，重启不会恢复。
- 尚未接入真实免费行情数据源，真实最新价和真实五档盘口尚未验证。
- UI 目前同步读取 Mock 数据，尚未实现后台 QThread/线程池刷新。
- 回测仍为基础骨架，不含完整卖出、组合再平衡、复权、分红、真实沪深300和财务披露时点控制。

## 下一步准确任务

1. 设计并实现账户仓储层，将账户、持仓、订单和成交事务性持久化到 SQLite。
2. 为首次初始化、成交后保存、重启恢复、T+1 可用数量和重复写入编写测试。
3. 将 `TradingAppService` 与运行时数据库路径接线，保证应用重启恢复。
4. 验证并接入合法免费行情数据源，实测最新价和五档盘口；缺失字段不得伪造。
5. 使用 QThread/线程池实现后台刷新和失败降级。
6. 扩展回测：卖出规则、组合再平衡、沪深300真实基准、复权/分红处理和财务披露时点控制。

## 下一条恢复命令或任务

从项目根目录执行恢复检查后，直接开始阶段 8：实现 `AccountRepository` 和 `SimulatedAccount` 的 SQLite 保存/恢复，并运行新增持久化测试与完整回归。
