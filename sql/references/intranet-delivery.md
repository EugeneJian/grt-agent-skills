# 内网 rd_delivery 查询与差异核对

出货权威目标已指定为 `oa_report.dbo.rd_delivery`，物料权威源仍为 `sap_material`。当前结构升级与历史验收尚未完成，保持 `report_only`。PostgreSQL 历史仅作一次性迁移输入；切换后本机与 Supabase 均由内网已提交版本发布。 详见 [SSOT 规则](rd-delivery-ssot.md)。本文五列及月度粒度描述当前已部署旧接口。

默认 `intranet` 使用 SQL Server 的 `oa_report.dbo.rd_delivery`，直接通过完整 PN 关联 `dbo.sap_material`，物料 SSOT 不再依赖云端副本。连接复用当前电脑的 `OA_HOST/OA_PORT/OA_USER/OA_PWD` 环境或既有被 Git 排除的 `sql/.env`；不要把凭据提交或复制进 Skill。安装 `pymssql` 后运行统一查询脚本。

`rd_delivery` 主键是 `(zyear,zmonth,matnr,country)`，数量是 `decimal(18,6)`。它没有销售单位、日级日期、来源文件和来源行号。查询动态探测现有年月；请求超出当前范围会报覆盖错误，不能称为零出货。已有年月还可能存在缺月或不完整，分析前核对实际月份及来源。

- `shipment_monthly`：按月、产品线汇总，PN 完整等值关联当前物料，限定 Z001、排除 Z0090，保留 NULL 系列及全部国家。
- `delivery_by_pn_month`：月、PN、运抵国、数量及当前产品线 / 机型。它不是日级交货明细。
- 两者均有 `_including_housing`；只有用户要求时使用。
- `material`：实时 `sap_material`，`synced_at=null`（直接查源库，没有副本同步时间），`source_present=true`。
- `shipment_detail`、`material_sync` 不在这个源提供；使用显式 `local` 或已授权 `cloud`。新增月度 PN 数据集未部署到云端，云端会拒绝它，不自动换数据集。

旧表单位未验证时，profile 的 `delivery_scope.sales_unit` 必须为 `UNSPECIFIED`。数量仅作为原表数量展示，不标 PCS、不与 M/KG/ROL 混加；传单位筛选会报错。`source_rows=null`，不能把汇总行数冒充 Excel 来源行数。先由维护流程逐键核对单一 PCS 期间，才可以配置 `from_month`、`through_month`、`sales_unit="PCS"`、`unit_verified=true`，并保留验收凭证；不能只改配置来制造已同步状态。

```json
{"dataset":"shipment_monthly","select":["month","product_line","sales_unit","amount"],"limit":500}
```

国家下钻：把数据集改为 `delivery_by_pn_month`，按 `month`（月首）和完整 `pn` 筛选。不存在日级 `date`。输出中说明内网覆盖、单位是否已验证及当前物料属性；不把历史旧表自动宣称为 Excel 完整副本。

目前维护通道可生成本机与内网差异报告，新增或修复须另有明确的批次授权和可用的服务端审计 / 来源去重方案。`rd_delivery` 的新增、更新权限不等于可以混入不同单位、覆盖旧统计或删除历史。原始完整来源继续保留本机 PostgreSQL 与 Excel 归档。
