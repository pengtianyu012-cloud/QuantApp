# Phase 1 SQLite 迁移说明

本说明适用于本地 SQLite 数据库从 v3 升级到 v4。应用启动时检查 schema_migrations，并在同一事务中执行结构变更、版本记录和索引创建；任一步失败都会回滚。

## 升级前备份

关闭应用后，在项目源码运行目录执行：

~~~powershell
Copy-Item .\data\quant_app.sqlite3 .\data\quant_app.pre-v4.sqlite3
~~~

冻结版数据库默认位于 %LOCALAPPDATA%\QuantApp\data\quant_app.sqlite3，应备份对应文件。

## v4 变更

signals 表新增：

- suggested_position_pct：策略建议的组合目标仓位。
- account_id：信号所属本地模拟账户。
- scheduled_for：计划执行的下一交易日。
- dispatch_status：not_scheduled、pending、order_created、skipped 或 rejected。
- order_id：成功派发后关联的模拟订单。
- dispatch_message、processed_at：派发审计结果与处理时间。

orders 表新增 signal_id。非空 signal_id 建立唯一索引，保证同一信号最多生成一笔订单；信号派发查询建立账户、状态和计划日期组合索引。

旧 v3 信号保留原始内容，新字段使用 not_scheduled、空账户和空计划日期作为兼容值，不会被误当成待派发收盘任务。旧订单的 signal_id 为 NULL，不影响手工订单和历史订单恢复。

## 一致性与恢复

收盘任务先把信号追加为 pending，再保存账户及 signal_id 关联订单，最后确认派发状态。若最后一步中断，重启后会从账户订单审计记录恢复关联并把 pending 修正为 order_created，不会创建第二笔订单。

账户保存失败时不会确认派发状态；信号保持 pending，后续可重试。信号、成交和订单事件历史不会因任务重跑被删除重建。

## 回退

v4 不提供原地降级 SQL。需要回退旧程序时，关闭应用并恢复升级前备份；先另存当前 v4 数据库，避免丢失升级后新增的信号派发审计和 signal_id 订单关联。
