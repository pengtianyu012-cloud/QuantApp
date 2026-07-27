# 数据源说明

当前已实现：

- `MarketDataProvider` 抽象接口
- `MockMarketDataProvider` 无网络行情源
- `FallbackMarketDataProvider` 主备降级包装器
- `TtlMemoryCache` 轻量 TTL 缓存
- 行情字段校验：最新价、昨收、成交量、成交额、时区、延迟、盘口价格和委托量

Mock 数据源支持：

- `get_stock_list()`
- `get_latest_quotes(symbols)`
- `get_order_book(symbol)`，包含买一到买五、卖一到卖五及委托量
- `get_intraday_bars(symbol, interval)`
- `get_daily_bars(symbol, start_date, end_date)`
- `get_trading_calendar(start_date, end_date)`
- `get_financial_indicators(symbols, report_date)`，仅为示例数据并带披露时点警告
- `health_check()`

真实数据源尚未接入。后续实现顺序：

1. 本地 CSV/Parquet 数据源：用于可重复回测。
2. 免费行情适配器：接入前必须检查官方文档和实际可用性。
3. 付费数据源扩展：仅提供配置入口，不提交密钥。

如果字段不存在，界面必须显示“数据源不支持”，不得伪造数值。

五档盘口中的买量/卖量表示委托量，不等同于实际成交量。内盘/外盘属于主动卖出/主动买入成交口径，必须由数据源明确支持后才展示。
