---
name: sql
description: 查询内网 SQL Server 的 oa_report 报表库（SAP 物料/库存/出货/预测）。当用户提到 oa_report、sap_material、rd_prd_stock、rd_delivery、rd_forecast、物料主数据、工厂库存、出货交付、需求预测、PowerBI 数据源，或要求查询内网 10.5.5.163 数据库时使用本 skill。只读查询，禁止写入。
---

# oa_report 报表库查询

内网 SQL Server 只读库，承载 SAP 同步的物料主数据、工厂库存、出货交付与需求预测，是 PowerBI 的数据源。

## 连接信息（只读账号，安全可控）

| 项 | 值 |
|---|---|
| 服务 | Microsoft SQL Server 2017 |
| 地址 | `10.5.5.163:1433`（内网，需在办公网/VPN 内；本机出口 IP 10.100.48.163） |
| 库 | `oa_report` |
| 账号 | 只读账号（仅 SELECT）；凭据保存在本地 `sql/.env`（不入 Git），或用 `OA_USER`/`OA_PWD` 环境变量提供 |

⚠️ 同 IP 的 3306 端口是另一个 MySQL 实例，与本库无关，不要连错。
⚠️ **严格只读**：只执行 SELECT；任何 INSERT/UPDATE/DELETE/DDL/DML 一律拒绝并提醒用户。

## 查询方式（优先用封装脚本）

```bash
# 依赖：pymssql（首次使用先装：pip3 install pymssql）
# 脚本位置：本 skill 目录下 scripts/query.py

# 方式1：SQL 文件
python3 <skill_dir>/scripts/query.py @查询.sql

# 方式2：heredoc / stdin
echo "SELECT TOP 10 * FROM sap_material" | python3 <skill_dir>/scripts/query.py

# 方式3：直接传 SQL 参数（注意 shell 转义）
python3 <skill_dir>/scripts/query.py "SELECT COUNT(*) FROM rd_delivery"

# 输出格式：--format ndjson（默认，每行一条 JSON，便于 jq/python 后处理）
#           --format table（对齐表格，适合直接展示）
# 凭据从本 skill 目录的 .env 自动加载（不入库）；也可用环境变量 OA_HOST / OA_PORT / OA_USER / OA_PWD / OA_DB 覆盖
```

脚本自带只读校验：词法级剥离字符串、注释与带引号标识符后，仅放行**单条** SELECT / WITH 语句，并整词拒绝 INTO、INSERT、EXEC 等写操作/过程调用关键字（`SELECT ... INTO`、`WITH ... INSERT` 变体会被拦下；字符串里的 'update' 等字样不会误拦）。该校验只是第一层防线，最终兜底是数据库只读账号自身的权限，两者不可互相替代。脚本打印行数；行数大的查询先 `SELECT COUNT(*)` 评估再决定是否加 TOP / WHERE / 聚合下推。

## 表结构与数据画像

完整字段说明见 [references/schema.md](references/schema.md)。速览：

| 表 | 行数 | 粒度 | 关键列 |
|---|---|---|---|
| `sap_material` | 17.9万 | 物料主数据(PK:MATNR) | MATNR(物料编码), MAKTX(物料描述), WGBEZ(物料组描述), MTART(物料类型), MSTAE(物料状态), ZGJ(国家,注意与出货country口径不同), ZJXXL/JXXL_TXT(机型系列), ZCPX/CPX_TXT(产品线), ZCPXL/CPXL_TXT(产品小类), ZCPFL/CPFL_TXT(产品分类), ZCPXF/CPXF_TXT(产品细分), ZGL(功率KW), ZMODEL(铭牌型号), CPXH(产品型号) |
| `rd_prd_stock` | 17万 | 月度快照(PK:年月+物料+工厂+库位) | stock(数量,跨月不可加总), meins(单位,需分组), LGOBE(库位描述) |
| `rd_forecast` | 3万 | 预测单(PK:zz_oaid+工厂+物料+需求日期) | zz_oaid(OA单号,单列不唯一), bdter(需求日期), bdmng(数量), zupdate(上传日期), crdate(建立日期) |
| `rd_delivery` | 1万 | 年月×物料×国家(PK含country) | doqty(发货数量,无单位字段), country(交付国家,中文,111个) |
| `uf_jxxl` | 220 | 机型系列字典 | ztext(名称), ZOWNERT(负责人) |
| `uf_cpx/cpxl/cpfl/cpxf` | 4~23 | 产品线/系列/分类/细分字典 | 编码→名称 |

**数据时间范围**：各表覆盖区间会演进，见 [references/query-patterns.md](references/query-patterns.md)；大表查询前先探测最新月份，不要硬编码。

## 标准查询模式

常用 SQL 模板（物料聚合/最新快照探测/出货趋势）与口径坑位（MATNR 匹配、MSTAE 过滤、stock 快照语义）见 [references/query-patterns.md](references/query-patterns.md)。首次写查询前先读它，可避开已知坑。

## 与飞书多维表格的联动

本库的 JXXL_TXT（机型系列）与飞书「古瑞瓦特认证多维表格」的「机型系列」「产品线ProductLine」字段同源，可做认证进度 × 库存/出货的交叉分析：先在本库按机型系列聚合业务数据，再到多维表格按同名系列过滤认证记录。
