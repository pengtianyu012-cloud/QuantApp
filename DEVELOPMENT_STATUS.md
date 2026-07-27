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

阶段 0：可恢复开发基线进行中。

## 已完成内容

- 已正确以 UTF-8 读取原始需求附件。
- 已确认当前工作区初始状态：根目录包含 `.venv`、`__pycache__`、`main.py`。
- 已确认当前没有 Git 仓库。
- 已确认 `DEVELOPMENT_STATUS.md` 原先不存在。
- 上一轮已在现有 `main.py` 基础上升级为 PySide6 六页原型，并通过语法和无界面实例化检查。

## 修改的文件

- `main.py`：上一轮升级，已验证但尚未提交。
- `DEVELOPMENT_STATUS.md`：本阶段新建。
- `.gitignore`：本阶段新建。

## 测试结果

上一轮已执行：

- `.\.venv\Scripts\python.exe -m py_compile main.py`：通过。
- `.\.venv\Scripts\python.exe -c "import main; print(main.TradingRules().benchmark)"`：通过，输出 `沪深300`。
- `.\.venv\Scripts\python.exe -c "from PySide6.QtWidgets import QApplication; import main; app = QApplication([]); window = main.QuantMainWindow(); print(window.windowTitle(), window.tabs.count())"`：通过，输出 `A股量化模拟交易系统 6`。

## 当前失败项

- 尚未初始化 Git，因此还没有稳定提交点。
- 尚未建立 `app/` 分层工程结构。
- 尚未实现数据库、行情接口、撮合、风控、策略、回测和完整测试。

## 下一步准确任务

1. 初始化 Git 仓库。
2. 提交阶段 0 可恢复基线。
3. 开始阶段 1：创建工程骨架、配置、日志、README、pyproject、requirements 和开发脚本。

## 下一条恢复命令或任务

从项目根目录执行：读取原始需求、读取 `DEVELOPMENT_STATUS.md`、查看 `git status --short` 和 `git log --oneline -5`，然后继续“阶段 1：P0 工程骨架与核心配置”。
