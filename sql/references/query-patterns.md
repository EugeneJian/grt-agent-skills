# 标准查询模式与口径坑位

## 数据时间范围（首次核实于 2026-10-16，查询时建议重新验证新鲜度）

- `rd_prd_stock`：2025-01 ~ 2026-09（月度快照）
- `rd_delivery`：2025 年（仅 7 个月有数，覆盖不全，用前先查）
- `rd_forecast`：需求日期 2024-02 ~ 2027-01；zupdate(上传日期)最大 2026-09-22，crdate(建立日期)最大 2026-09-23

## 标准查询模式

```sql
-- 物料维度聚合：业务表 JOIN 主数据取产品维度（维度列均有 *_TXT 冗余，可免 JOIN）
-- stock 必须按 meins 单位分组，不同单位的数量不能混加
SELECT m.CPXF_TXT, s.meins, s.zyear, s.zmonth, SUM(s.stock) stock
FROM rd_prd_stock s JOIN sap_material m ON s.matnr = m.MATNR
WHERE s.zyear*100+s.zmonth = 202609
GROUP BY m.CPXF_TXT, s.meins, s.zyear, s.zmonth;

-- 最新快照月份（不要硬编码，先探测）
SELECT MAX(zyear*100+zmonth) FROM rd_prd_stock;

-- 机型系列级出货趋势（uf_jxxl 与 sap_material.ZJXXL 同编码）
SELECT d.country, SUM(d.doqty) qty
FROM rd_delivery d JOIN sap_material m ON d.matnr = m.MATNR
WHERE d.zyear = 2025
GROUP BY d.country ORDER BY qty DESC;
```

## 口径坑位

- MATNR 大小写不敏感（默认排序规则），物料号格式不统一（如 `150.0045200`、`:B710.ZT0012300`），跨表匹配一律等值 JOIN、不要截断（主表 40 位，业务表 18 位）
- MSTAE 常见值：`' '`(在用 15.4万)、`Z1`/`Z3`/`Z4`(各类状态)，统计在役物料时需过滤
- `rd_prd_stock` 为月度快照：当前库存取最新月末值，跨月累加无意义；不同 meins 单位分组统计
- `sap_material.ZGJ`（国家）与 `rd_delivery.country` 口径不同，不能混用
- 完整字段字典见 [schema.md](schema.md)
