# 数据质量检查

当前已实现 `DataQualityService`，用于检查 Mock 数据源的基础质量。

已检查内容：

- 股票列表必填字段：symbol、code、exchange、name、listed_date
- 股票列表重复代码数量
- 最新行情字段：最新价、昨收、成交量、成交额、行情时间时区、行情延迟
- 五档盘口字段：买卖五档数量、盘口价格、盘口委托量

当前边界：

- 仅验证 Mock 数据源。
- 尚未写入 `data_quality_reports` 数据库表。
- 尚未接入真实数据源字段漂移检测。
- 尚未提供 UI 一键导出诊断包。
