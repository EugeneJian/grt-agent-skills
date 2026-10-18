# 两种通道共用的查询约定

## 请求

```json
{
  "dataset": "shipment_monthly",
  "select": ["month", "product_line", "sales_unit", "amount"],
  "filters": [
    {"column":"month","op":"gte","value":"2026-09-01"},
    {"column":"month","op":"lt","value":"2026-10-01"},
    {"column":"sales_unit","op":"eq","value":"PCS"}
  ],
  "order": [{"column":"month","direction":"asc"}],
  "limit": 500,
  "offset": 0
}
```

数据集：`shipment_monthly`、`shipment_detail`、对应的 `*_including_housing`、`material`、`material_sync`。字段和类型来自 [datasets.json](datasets.json)。省略 `select` 取该数据集全部允许字段；字段选择不会去重或重新聚合。

筛选是 AND；支持 `eq/gt/gte/lt/lte/in/isnull`。`in` 接受 1–100 个同类型值，`isnull` 接受布尔值。日期为 `YYYY-MM-DD`，时间戳使用带时区 ISO 8601；文本保留前导零。最多 30 个条件。不能传表达式、JOIN、SQL 或自定义函数。

排序仅允许已选择列的 `asc/desc`，NULL 总在最后，脚本补足已选择字段作并列排序。不同数据库文本排序规则可能不同；跨通道核对应按字段和值比较。

每页默认 500 行，受 profile 的 `max_rows`（默认 1000，上限 10000）约束。若 API 服务端页上限更小，以实际返回行数为准。`offset` 从 0 开始，下一页加 `returned_rows`。所有页面必须使用相同 profile 和查询条件；同步过程中分页不保证同一快照。

`shipment_monthly` 已按月、产品线编码 / 描述、销售单位汇总。需要年度合计时，在读完所有月份后按单位求和；不要把 `source_rows` 当出货量。国家或 PN 下钻使用 `shipment_detail` 并限定期间，分页读取后按完整 PN / 国家 / 单位汇总。大范围复杂聚合可由数据维护方增加专用数据集，避免把所有明细重复传给 Agent。

## 响应

```json
{"profile":"cloud","dataset":"shipment_monthly","rows":[],"returned_rows":0,"total_rows":0,"offset":0,"has_more":false,"elapsed_ms":0}
```

`total_rows` 是匹配结果行数，不是数量合计；`has_more` 表示仍有未返回行。数量为 JSON 整数或精确十进制字符串，下游用 Decimal 解析，禁止浮点近似或混加单位。`elapsed_ms` 包含客户端连接与取数时间，不是数据库执行计划耗时。

错误写入 stderr，退出码 2；成功退出码 0。连接失败、401/403、缺少凭据均不代表零出货；没有匹配数据必须是成功响应且 `total_rows=0`。

## 新鲜度

查 `material_sync`：筛选 `status='complete'`，按 `source_extracted_at desc` 排序取最新一行。明细按 `date desc` 取一行可确认当前可见截止日。`material.synced_at` 是写入副本时间，`source_extracted_at` 才是抽取源库的时间。两通道核对前先确认它们使用同一批数据及同一视图版本。
