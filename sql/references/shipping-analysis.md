# 历史出货查询与业务口径

## 入口与权限

- 内网默认入口详见 [rd_delivery 口径](intranet-delivery.md)。以下视图、来源行和单位规则适用于显式 `local` / `cloud` 完整来源通道。
- 完整来源查询入口是 `scripts/query_data.py`，必须显式选择 `--profile local` 或 `--profile cloud`，不依赖 MCP。
- 本机 `local` 用于同步验证，需显式指定；也可用 `compare_profiles.py --left local --right cloud` 核对两端。内网是默认入口，但目前只有原月度表，不能假定已同步完整来源。其他 Agent 主机需配置自己的云端授权会话，接入见 [connections.md](connections.md)。
- 云端副本项目由所在环境的 profile 绑定；共享 Skill 不硬编码实际项目坐标，客户端凭据不随 Skill 分发。
- 本 Skill 不调用迁移、写入或同步工具。原 `scripts/query.py` 仅支持 SQL Server，不接收 PostgreSQL 查询。

## 默认统计口径

使用 `shipment_detail` 或 `shipment_monthly` 数据集，映射到 `shipping.report_shipments` / `shipping.report_product_line_monthly`。视图已经统一执行：

- PN 匹配当前 `master_data.sap_material`，物料类型 `MTART='Z001'`，且 `source_present=true`（当前源库仍存在）。
- 不含机型系列编码 `Z0090`（机壳）。使用 `IS DISTINCT FROM` 保留 NULL 系列。
- 保留所有国家，包括无法映射的国家；空运抵国名称显示“通用”。国家来自出货，不用物料国家替换。
- 保留 Power Query 兼容的原来源行和跨文件重叠，禁止静默去重。当前 JSON 白名单没有 `_deduplicated` 数据集；用户要求去重时，先确认重叠判定及获授权的数据入口，不能猜测数据集名称或用 DISTINCT 替代。
- 数量必须按 `sales_unit` 分组，或显式限定 `sales_unit='PCS'`。其他单位不得混加。

PN 以完整文本关联 `pn_key=upper(btrim(pn))`，不截断、不去前导零。产品线和机型等属性直接取物料副本，不需要“机型系列＋产品线”DIM 表。不要额外套用在役物料、非 OTHERS 分类或已识别国家等筛选。

## 视图与字段

| 查询用途 | 对象 |
|---|---|
| 默认月度出货 | `shipping.report_product_line_monthly` |
| 默认明细 / PN / 国家下钻 | `shipping.report_shipments` |
| 含机壳的完整 Z001 月度出货 | `shipping.report_product_line_monthly_including_housing` |
| 含机壳的完整 Z001 明细 | `shipping.report_shipments_including_housing` |
| 当前物料分析副本 | `master_data.sap_material` |
| 所有物料类型、含机壳的完整关联核对 | `shipping.shipments_enriched_power_query` |
| 来源行追溯 / 文件完成状态 | `shipping.shipment_facts` / `shipping.source_reconciliation` |

月度字段：`month`（月首 date）、`product_line_code`、`product_line`、`sales_unit`、`amount`、`source_rows`。

明细字段：`date`（过账日期）、`pn`、`amount`、`country_name`、`sales_unit`；以及 `product_line_code/product_line`、`model_series_code/model_series`、`product_category_code/product_category`、`product_subcategory_code/product_subcategory`、`product_segment_code/product_segment`、`product_model`、`power_kw`、`material_description`、`material_type`。

物料副本主要字段：`matnr`、`pn_key`、`maktx`、`mtart`、`mstae`、`zcpx/cpx_txt`、`zjxxl/jxxl_txt`、`zcpfl/cpfl_txt`、`zcpxl/cpxl_txt`、`zcpxf/cpxf_txt`、`cpxh`、`zmodel`、`zgl`、`ersda`、`laeda`、`synced_at`、`source_present`。这些是同步时的当前属性，不是历史分类快照；内网 `oa_report.dbo.sap_material` 仍为 SSOT。

## 维度与下钻语义（唯一业务口径）

所有出货示例、查询约定和下游分析以本节为准。字段是否可查询以 [datasets.json](datasets.json) 为准；不能把业务层级当作额外服务端字段。

| 业务维度 | 当前来源 / 字段 | 用法 |
|---|---|---|
| 产品线 | `product_line_code/product_line` ← `ZCPX/CPX_TXT` | 默认第一级 |
| 机型系列 | `model_series_code/model_series` ← `ZJXXL/JXXL_TXT` | 产品线下第二级；编码可能跨线重复，键必须含祖先产品线编码 |
| 铭牌型号 | `material.zmodel` ← `ZMODEL` | 可选下钻；当前明细不直接暴露，按下述两阶段关联 |
| 功率 | `power_kw` ← `ZGL`（kW） | 可选分组 / 筛选，保留原值；不是出货数量 |
| PN | `pn`，物料键 `pn_key` | 可选最细物料层；完整文本，规范化为 upper(trim(PN)) |
| 产品型号 | `product_model` ← `CPXH` | 单独的可选属性，不能冒充铭牌型号 |
| 国家 | 出货原始运抵国 `country_name` | 独立分析轴，不能用物料 `ZGJ` 替换 |
| 时间 | 出货 `date`（过账日）；`month` 为其月份 | 独立分析轴，不能用主数据创建 / 同步日替换 |

默认路径为产品线 → 机型系列，再按问题选择铭牌型号、功率和 PN；并非每次必须经过所有层级。铭牌型号可以对应多个 PN，也可跨系列重复，不能当作唯一物料键。`ZGGXH` 是源库“规格型号”，当前云端白名单无此字段；不得强制要求它，也不能由 CPXH/ZMODEL 猜出。用户说“型号 / 规格”有歧义时先区分所需字段。

国家和时间可与任一级交叉分析。空运抵国映射的“通用”表示未知 / 未提供，不表示已识别的全球市场。未知国家、系列、铭牌、功率等维度不得因下钻被丢弃；统一展示为未知并保留相应数量。不要把一个国家或单一功率强制归属于某个系列。

产品分类和物料属性来自同步时的当前 SAP 主数据，不是出货发生时的历史分类快照。结果必须披露这一点及数据截止 / 抽取时间。

### 铭牌型号：两阶段完整分页关联

当前统一 JSON 接口不接受 JOIN；`shipment_detail` 没有 `zmodel`。不能把 `zmodel` 塞进明细 select/filter。需要铭牌时：

1. 在选定 profile 上读取期间内 `shipment_detail` 的全部页，保留 PN、amount、sales_unit、date 和所需维度；`has_more=true` 时下一页 offset 加实际 `returned_rows`，其他条件不变。
2. 由明细生成规范化完整 PN 的集合，仅用于物料查找（不是去重出货）。按每批最多 100 个 PN 查询 `material`，筛选 `pn_key in [...]`、`source_present=true`，选 `pn_key/zmodel/source_present`；每批也必须读完全部页。
3. 在分析环境左关联到每一条原始出货行。每个规范化 PN 最多一个物料映射；重复键即停止检查，禁止多对多放大。无匹配或空铭牌进入未知组，不能内连接丢失数量。不得因两阶段查询暂时无匹配就删除已经返回的出货行。
4. 若用户指定铭牌过滤，先完整关联，再显式过滤；其合计只能与相同过滤口径的父级核对。记录关联缺失与副本批次；同步跨页变化时重查稳定批次，不宣称快照一致。

可运行的纯本地 [合成下钻示例](drilldown_example.py) 接收已完整分页的行，演示左关联、祖先键、Decimal 和分单位汇总；它不连接数据库，不替代完整分页或服务端视图。合成语义与查询示例测试：在 Skill 仓库根目录运行 `python3 -m unittest discover -s sql/tests`；这些测试不证明线上视图或副本已更新。

### 汇总与核对

- `shipment_monthly` 仅按月、产品线、单位预汇总；系列、铭牌、功率、PN、国家均应从 `shipment_detail` 完整读取后聚合。不能从月度总量反推这些维度。
- 父子核对必须使用相同数据集（是否含机壳）、期间、国家 / 其他筛选、单位、副本批次和来源行口径。每单位的子级之和等于父级；可选维度缺失进入未知组。不同单位永不相加。
- 用 `amount` 的精确 Decimal 求和；`source_rows/total_rows` 是行数，`power_kw` 是功率，均不是出货量。退货等负值保留，不擅自取绝对值。
- 缺失月份不自动补零；仅知道最大过账日不能证明中间月份完整。未经覆盖核验的缺月应标记缺失 / 未知；无匹配数据与连接失败分开说明。

## 查询示例

按 [查询约定](query-contract.md) 核实时间覆盖与物料同步时间。普通月度分析可复用 [九月全部产品线及单位](september-2026-all-lines.json)；截图专项核对用 [九月十条线](september-2026.json) / [1–9 月十条线](january-september-2026.json)。更换 profile 后仍使用相同文件：

```bash
python3 <skill_dir>/scripts/query_data.py --profile local @<skill_dir>/references/september-2026-all-lines.json
python3 <skill_dir>/scripts/compare_profiles.py --left local --right cloud @<skill_dir>/references/september-2026-all-lines.json
```

系列 / 功率 / PN / 国家下钻使用 [明细查询示例](shipment-drilldown.json)，铭牌在完整分页后按上述两阶段补充。PN 筛选也可使用以下 JSON。分页读完，再按 PN、国家和销售单位聚合数量；不能省略其他页面或用 DISTINCT 丢掉重复来源行：

```json
{"dataset":"shipment_detail","filters":[{"column":"date","op":"gte","value":"2026-08-01"},{"column":"date","op":"lt","value":"2026-09-01"},{"column":"pn","op":"eq","value":"完整PN"}],"limit":500}
```

只有用户要求计入机壳时，才将 JSON 的 `dataset` 改为 `shipment_detail_including_housing` 或 `shipment_monthly_including_housing`（SQL 视图名不是 JSON 数据集名）。查询机壳本身时也必须使用含机壳入口，再限定 `model_series_code='Z0090'`。

查询示例中的日期和产品线名单用于指定筛选范围，不包含业务结果。专项核对的产品线范围不代表全部产品线，普通查询不能自动沿用该名单。

副本未配置自动刷新。每次分析先通过授权查询确认实际覆盖期间、物料同步批次和截止日期；不完整年度必须在结果中说明。验收时使用同一份 JSON 对两端全部页面逐项比较，统计结果及核对报告仅保存在授权环境，不写入公开 Skill。

## 与内网库存 / 预测联合分析

先通过选定通道按完整 PN、期间、销售单位汇总出货，再通过原 `scripts/query.py` 查询内网库存或预测。在分析环境按完整 PN 的大小写不敏感等值语义连接；分别聚合后关联，避免明细多对多放大。

内网库存取实际最新快照月，保留 `meins`，不能跨月累加为当前库存。预测与 `rd_delivery` 没有独立单位字段，比较前需核实口径。两套数据库之间不能直接写普通跨库 JOIN；内网默认使用 `rd_delivery` 月度表，覆盖、单位与本机 / 云端来源可能不同，不将两处出货数量相加。

当前物料实时核验、云端未同步字段及最新库存 / 预测仍查询内网。物料副本未刷新时，在结果中说明同步日期；本 Skill 不自动触发全量同步。

