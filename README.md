# A股量化模拟交易系统

这是一个面向 Windows 10/11 的桌面端 A股量化模拟交易系统。项目当前处于学习与开发同步阶段，第一目标是建立可运行、可测试、可恢复开发的本地模拟交易软件。

重要免责声明：本软件仅用于量化研究和模拟交易，不构成投资建议，不连接真实券商，不执行真实订单。

## 当前状态

- 已完成 PySide6 桌面端启动骨架。
- 已建立 `app/` 分层结构、配置模块、日志模块和 10 个核心页面骨架。
- 已实现可重复测试的 Mock 行情数据源；尚未接入真实行情数据源。
- 已实现 SQLite 初始化、Mock行情、A股交易规则、交易成本、模拟账户、风控检查和撮合可成交性内核，并已接入总览、实时行情、市场数据和模拟交易页面；尚未实现策略和回测。
- 未实现功能会在界面中标注“尚未实现”。

## 技术栈

- Python 3.11
- PySide6
- pandas、numpy、SQLAlchemy：后续数据与回测阶段使用
- SQLite：后续本地持久化阶段使用
- unittest/pytest：当前可用标准库测试，后续补 pytest
- ruff：安装后用于静态检查
- PyInstaller：Windows 打包配置

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

当前虚拟环境尚未安装 pytest，阶段1使用标准库测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
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

当前环境依赖探查显示 PySide6 已安装，pandas、numpy、SQLAlchemy、pytest、ruff、PyInstaller 尚未安装。后续如允许修改虚拟环境，可执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 数据源说明

当前已完成统一 `MarketDataProvider` 抽象接口和 Mock 行情数据源。Mock 支持股票列表、最新行情、五档盘口、分时、日线、交易日历、财务指标示例和健康检查；真实数据源尚未接入。任何未被实际验证的数据字段都不会在界面中伪造成可用。

五档盘口中的买量/卖量表示委托量，不等同于实际成交量。内盘/外盘属于主动卖出/主动买入成交口径，必须由数据源明确支持后才展示。

## 模拟交易规则

- 初始资金：100,000 元
- 单股仓位上限：30%
- 总仓位上限：90%
- 最大回撤达到 15% 暂停新增买入
- 普通A股买入数量为 100 股整数倍
- 支持 T+1 规则
- 停牌、涨跌停无法成交时订单顺延

以上规则当前已进入配置模块、可测试内核和桌面端模拟交易页。手工模拟买入/卖出会先二次确认，并且只在软件内部生成模拟订单。

## Windows 打包

```powershell
.\scripts\build_windows.ps1
```

当前仅提供打包脚本。只有在 PyInstaller 安装并实际运行成功后，才可声称生成了可用 exe。



