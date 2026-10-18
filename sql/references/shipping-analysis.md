# 历史出货查询与业务口径

## 入口与权限

- 默认入口是 `scripts/query_data.py`，省略 `--profile` 时使用标准配置的 `cloud`（Supabase HTTPS API）。日常出货和物料副本分析默认查云端，不依赖 MCP。
- 本机 `local` 用于同步验证，需显式指定；也可用 `compare_profiles.py --left local --right cloud` 核对两端。公司 `intranet` 仍需部署后显式选择。其他 Agent 主机需配置自己的云端授权会话，接入见 [connections.md](connections.md)。
- 云端副本项目由所在环境的 profile 绑定；共享 Skill 不硬编码实际项目坐标，客户端凭据不随 Skill 分发。
- 本 Skill 不调用迁移、写入或同步工具。原 `scripts/query.py` 仅支持 SQL Server，不接收 PostgreSQL 查询。

## 默认统计口径

使用 `shipment_detail` 或 `shipment_monthly` 数据集，映射到 `shipping.report_shipments` / `shipping.report_product_line_monthly`。视图已经统一执行：

- PN 匹配当前 `master_data.sap_material`，物料类型 `MTART='Z001'`。
- 不含机型系列编码 `Z0090`（机壳）。使用 `IS DISTINCT FROM` 保留 NULL 系列。
- 保留所有国家，包括无法映射的国家；空运抵国名称显示“通用”。国家来自出货，不用物料国家替换。
- 保留来源行和跨文件重叠；只有显式要求排除已核对的文件重叠时才使用 `_deduplicated` 版本。
- 数量必须按 `sales_unit` 分组，或显式限定 `sales_unit='PCS'`。其他单位不得混加。

PN 以完整文本关联 `pn_key=upper(btrim(pn))`，不截断、不去前导零。产品线和机型等属性直接取物料副本，不需要“机型系列＋产品线”DIM 表。不要额外套用在役物料、非 OTHERS 分类或已识别国家等筛选。

## 视图与字段

| 查询用途 | 对象 |
|---|---|
| 默认月度出货 | `shipping.report_product_line_monthly` |
| 默认明细 / PN / 国家下钻 | `shipping.report_shipments` |
| 含机壳的完整 Z001 月度出货 | `shipping.report_product_line_monthly_including_housing` |
| 含机壳的完整 Z001 明细 | `shipping.report_shipments_including_housing` |
| 另排除文件重叠 | 对上述任一名称追加 `_deduplicated` |
| 当前物料分析副本 | `master_data.sap_material` |
| 所有物料类型、含机壳的完整关联核对 | `shipping.shipments_enriched_power_query` |
| 来源行追溯 / 文件完成状态 | `shipping.shipment_facts` / `shipping.source_reconciliation` |

月度字段：`month`（月首 date）、`product_line_code`、`product_line`、`sales_unit`、`amount`、`source_rows`。

明细字段：`date`（过账日期）、`pn`、`amount`、`country_name`、`sales_unit`；以及 `product_line_code/product_line`、`model_series_code/model_series`、`product_category_code/product_category`、`product_subcategory_code/product_subcategory`、`product_segment_code/product_segment`、`product_model`、`power_kw`、`material_description`、`material_type`。

物料副本主要字段：`matnr`、`pn_key`、`maktx`、`mtart`、`mstae`、`zcpx/cpx_txt`、`zjxxl/jxxl_txt`、`zcpfl/cpfl_txt`、`zcpxl/cpxl_txt`、`zcpxf/cpxf_txt`、`cpxh`、`zmodel`、`zgl`、`ersda`、`laeda`、`synced_at`、`source_present`。这些是同步时的当前属性，不是历史分类快照；内网 `oa_report.dbo.sap_material` 仍为 SSOT。

## 查询示例

按 [查询约定](query-contract.md) 核实时间覆盖与物料同步时间。普通月度分析可复用 [九月全部产品线及单位](september-2026-all-lines.json)；截图专项核对用 [九月十条线](september-2026.json) / [1–9 月十条线](january-september-2026.json)。更换 profile 后仍使用相同文件：

```bash
python3 <skill_dir>/scripts/query_data.py @<skill_dir>/references/september-2026-all-lines.json
python3 <skill_dir>/scripts/compare_profiles.py --left local --right cloud @<skill_dir>/references/september-2026-all-lines.json
```

PN / 国家下钻使用 `shipment_detail`，例如以下 JSON。分页读完，再按 PN、国家和销售单位聚合数量；不能省略其他页面或用 DISTINCT 丢掉重复来源行：

```json
{"dataset":"shipment_detail","filters":[{"column":"date","op":"gte","value":"2026-08-01"},{"column":"date","op":"lt","value":"2026-09-01"},{"column":"pn","op":"eq","value":"完整PN"}],"limit":500}
```

只有用户要求计入机壳时，才改用 `report_shipments_including_housing` 或其月度视图。查询机壳本身时也必须使用含机壳入口，再限定 `model_series_code='Z0090'`。

查询示例中的日期和产品线名单用于指定筛选范围，不包含业务结果。专项核对的产品线范围不代表全部产品线，普通查询不能自动沿用该名单。

副本未配置自动刷新。每次分析先通过授权查询确认实际覆盖期间、物料同步批次和截止日期；不完整年度必须在结果中说明。验收时使用同一份 JSON 对两端全部页面逐项比较，统计结果及核对报告仅保存在授权环境，不写入公开 Skill。

## 与内网库存 / 预测联合分析

先通过选定通道按完整 PN、期间、销售单位汇总出货，再通过原 `scripts/query.py` 查询内网库存或预测。在分析环境按完整 PN 的大小写不敏感等值语义连接；分别聚合后关联，避免明细多对多放大。

内网库存取实际最新快照月，保留 `meins`，不能跨月累加为当前库存。预测与 `rd_delivery` 没有独立单位字段，比较前需核实口径。两套数据库之间不能直接写普通跨库 JOIN；`rd_delivery` 覆盖不全，默认历史出货不使用它替代 Supabase，也不将两处出货数量相加。

当前物料实时核验、云端未同步字段及最新库存 / 预测仍查询内网。物料副本未刷新时，在结果中说明同步日期；本 Skill 不自动触发全量同步。
