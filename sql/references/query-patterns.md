# 标准查询模式与口径坑位

## 查询前验证数据时间范围

- `rd_prd_stock`：查询最新快照年月，当前库存只取该期。
- `rd_delivery`：先查可用年月及缺失月份，不假定覆盖完整。
- `rd_forecast`：分别探测 bdter（需求日期）、zupdate（上传日期）、crdate（建立日期），不能互相替代。

## 标准查询模式

```sql
-- 物料维度聚合：业务表 JOIN 主数据取产品维度（维度列均有 *_TXT 冗余，可免 JOIN）
-- stock 必须按 meins 单位分组，不同单位的数量不能混加
SELECT m.CPXF_TXT, s.meins, s.zyear, s.zmonth, SUM(s.stock) stock
FROM rd_prd_stock s JOIN sap_material m ON s.matnr = m.MATNR
WHERE s.zyear*100+s.zmonth = (SELECT MAX(zyear*100+zmonth) FROM rd_prd_stock)
GROUP BY m.CPXF_TXT, s.meins, s.zyear, s.zmonth;

-- 最新快照月份（不要硬编码，先探测）
SELECT MAX(zyear*100+zmonth) FROM rd_prd_stock;

-- 机型系列级出货趋势（uf_jxxl 与 sap_material.ZJXXL 同编码）
SELECT d.country, SUM(d.doqty) qty
FROM rd_delivery d JOIN sap_material m ON d.matnr = m.MATNR
WHERE d.zyear = (SELECT MAX(zyear) FROM rd_delivery)
GROUP BY d.country ORDER BY qty DESC;
```

## 口径坑位

- MATNR 大小写不敏感（默认排序规则），物料号格式不统一（如 `150.0045200`、`:B710.ZT0012300`），跨表匹配一律等值 JOIN、不要截断（主表 40 位，业务表 18 位）
- MSTAE 状态筛选以已确认的业务规则为准；不能将库存的在役筛选自动套到历史出货
- `rd_prd_stock` 为月度快照：当前库存取最新月末值，跨月累加无意义；不同 meins 单位分组统计
- `sap_material.ZGJ`（国家）与 `rd_delivery.country` 口径不同，不能混用
- 完整字段字典见 [schema.md](schema.md)
