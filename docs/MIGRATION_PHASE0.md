# Phase 0 本地数据库迁移

## 适用范围

本说明适用于本地 SQLite 数据库从 v2 升级到 v3。应用启动时自动检查 schema_migrations，并在单个事务中完成升级。迁移失败会回滚，不会提交半完成结构。

源码运行的默认数据库位于 data/quant_app.sqlite3；Windows 打包版位于 %LOCALAPPDATA%\QuantApp\data\quant_app.sqlite3。

## 升级前备份

关闭应用后复制数据库：

```powershell
Copy-Item .\data\quant_app.sqlite3 .\data\quant_app.pre-v3.sqlite3
```

打包版可复制 %LOCALAPPDATA%\QuantApp\data\quant_app.sqlite3。不要在应用正在写入时复制或替换数据库。

## v3 变更

- accounts 新增 peak_total_assets、current_drawdown 和 cumulative_fees；max_drawdown 与 risk_status 不再写死。
- orders 新增 eligible_at、filled_quantity 和 remaining_quantity。
- 新增 order_events，按状态变化追加审计记录。
- fills 新增 market_impact 和 reference_price；既有成交的 reference_price 迁移为原成交价。
- portfolio_snapshots 新增 trade_date、net_value、peak_total_assets、current_drawdown 和 cumulative_fees，并按账户/交易日保持一条记录。

## 历史数据映射

- filled_quantity 由同一订单既有 fills.quantity 求和。
- remaining_quantity 由 quantity - filled_quantity 推导。
- 旧待提交/待成交状态映射为 ELIGIBLE。
- 每个旧订单补种一条迁移时状态事件，不改写既有订单号和成交号。
- 同一账户同一交易日存在多条旧快照时保留时间最晚的一条，然后建立每日唯一约束。
- 旧账户峰值取 initial_cash 与 total_assets 的较大值；后续由每日快照持续更新。

## 成本口径

成交价已经包含滑点和市场冲击。现金只额外扣除或收取佣金、印花税和过户费；滑点和市场冲击不会再次作为现金费用扣除。

累计费用采用经济成本口径：

```text
累计费用 = 佣金 + 印花税 + 过户费 + 滑点 + 市场冲击
```

以参考行情估值时：

```text
总资产 = 初始资产 + 交易损益 - 累计经济成本
```

## 运行模式配置

新配置使用 QUANT_APP_MODE=mock、research 或 paper。旧 QUANT_APP_DATA_PROVIDER=public 仍映射为 research，仅用于兼容；research 禁止手工订单，paper 才允许真实公开行情下的本地模拟盘。research 和 paper 均禁止隐式 Mock。

## 回退

v3 不提供原地降级 SQL。需要回退旧程序时，关闭应用并恢复升级前备份。恢复前先保留当前 v3 数据库，以免丢失升级后新增的订单状态事件、成交和净值快照。
