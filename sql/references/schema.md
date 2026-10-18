# oa_report 完整 Schema 参考（权威字段字典版）

SQL Server 2017 · 库 `oa_report` · 只读账号（凭据见本地 `.env`，不入库）
字段类型、可空、主键、中文含义来自源库注释与已核对的关联；查询时重新验证数据范围与新鲜度。本公开字典不保存业务行数、状态分布或数量合计。

## sap_material（SAP 物料主数据，PK: MATNR）

| 列 | 类型 | 空 | 中文含义 | 说明 |
|---|---|---|---|---|
| MATNR | varchar(40) | 否 | 物料编码 | 保持字符串；业务表 matnr 为 18 位，**不要截断主表编码** |
| MAKTX | nvarchar(40) | 否 | 物料描述 | |
| ZGGXH | nvarchar(200) | 否 | 规格型号 | |
| MATKL | varchar(10) | 是 | 物料组 | |
| WGBEZ | nvarchar(20) | 是 | 物料组描述 | 如"充电桩""钣金" |
| MTART | char(4) | 是 | 物料类型 | Z002 等 |
| SPART | char(2) | 是 | 产品组 | |
| MSTAE | char(2) | 是 | 物料状态 | 在役物料统计按已确认的业务规则筛选；不能自动将该筛选套到历史出货 |
| ZGJ | nvarchar(20) | 是 | **国家** | 物料维度的国家字段；与 rd_delivery.country 业务口径**不同**，不可互作主键；国家维表关联尚未验证 |
| ZJXXL | varchar(20) | 是 | 机型系列编码 | → uf_jxxl.zjxxl（Z0221 在字典缺失） |
| JXXL_TXT | nvarchar(60) | 是 | 机型系列描述 | 冗余列，免 JOIN |
| ZCPX | varchar(20) | 是 | 产品线编码 | → uf_cpx.bh；产品线维度独立于产品分类路径 |
| CPX_TXT | nvarchar(50) | 是 | 产品线描述 | 如 T012 储能电池、T016 动力电池 |
| ZCPXL | varchar(20) | 是 | 产品小类编码 | → uf_cpxl.zcpxl（注意：是"产品小类"，不是系列） |
| CPXL_TXT | nvarchar(50) | 是 | 产品小类描述 | |
| ZCPFL | varchar(20) | 是 | 产品分类编码 | → uf_cpfl.zcpfl |
| CPFL_TXT | nvarchar(50) | 是 | 产品分类描述 | |
| ZCPXF | varchar(20) | 是 | 产品细分编码 | → uf_cpxf.zcpxf |
| CPXF_TXT | nvarchar(50) | 是 | 产品细分描述 | 与飞书认证表「产品线ProductLine」口径最接近 |
| ZGL | numeric(10,3) | 是 | 功率(KW) | 原始单位 kW，保留原值，异常值需单独复核 |
| ZZBNX | int | 是 | 质保年限 | |
| REVLV | char(2) | 是 | 版次 | |
| ZMODEL | nvarchar(20) | 是 | 铭牌型号 | 与 CPXH(产品型号)、ZGGXH(规格型号) 区分 |
| ERSDA | date | 是 | 物料创建日期 | |
| CREATED_AT_TIME | char(8) | 是 | 物料创建时间 | **物料创建时间**，不是工具读取或数据库同步时间 |
| LAEDA | date | 是 | 物料修改日期 | |
| ZBETA | nvarchar(10) | 是 | BETA样机状态 | |
| CPXH | nvarchar(200) | 是 | 产品型号 | |

## rd_prd_stock（工厂库存月度快照，PK: zyear+zmonth+matnr+werks+lgort）

| 列 | 类型 | 空 | 中文含义 | 说明 |
|---|---|---|---|---|
| zyear / zmonth | int | 否 | 年 / 月 | 快照年月 |
| matnr | varchar(18) | 否 | 物料 | → sap_material.MATNR |
| werks | varchar(4) | 否 | 工厂 | |
| lgort | varchar(10) | 否 | 库位 | |
| LGOBE | varchar(40) | 是 | 库位描述 | 如"惠州包装仓" |
| stock | decimal(18,2) | 是 | 数量 | **月度快照：跨月不可加总为当前库存**，趋势分析取各月末值 |
| meins | varchar(10) | 是 | 单位 | 与 stock 同行对应；**不同单位必须分组统计** |

- 时间范围和工厂范围由授权查询取得，不以文档中的历史画像代替当前数据。

## rd_delivery（出货交付，PK: zyear+zmonth+matnr+country）

| 列 | 类型 | 空 | 中文含义 | 说明 |
|---|---|---|---|---|
| zyear / zmonth | int | 否 | 年 / 月 | |
| matnr | varchar(18) | 否 | 物料 | → sap_material.MATNR |
| country | varchar(20) | 否 | 国家 | 交付国家名称（中文）；与物料 ZGJ 口径不同，不可直接互作主键 |
| doqty | decimal(18,6) | 是 | 发货数量 | 本表**没有独立单位字段** |

- 覆盖可能不完整，时间序列分析前先 `SELECT zyear*100+zmonth AS ym, COUNT(*) AS cnt FROM rd_delivery GROUP BY zyear*100+zmonth` 验证缺失月份（SQL Server 不支持 `GROUP BY 1` 位序写法，须写出完整分组表达式）。

## rd_forecast（需求预测，PK: zz_oaid+werks+matnr+bdter）

| 列 | 类型 | 空 | 中文含义 | 说明 |
|---|---|---|---|---|
| zz_oaid | varchar(40) | 否 | OA ID | **复合主键一部分，单列不唯一** |
| werks | varchar(4) | 否 | 工厂 | |
| matnr | varchar(18) | 否 | 物料编号 | → sap_material.MATNR |
| bdter | date | 否 | 需求日期 | 需求发生日期，**不是记录创建日期**；颗粒度多为月末 |
| bdmng | decimal(18,2) | 是 | 数量 | 预测需求数量；本表没有独立单位字段 |
| zupdate | date | 是 | 上传日期 | 不能解释为物料修改时间或已确认的同步时间 |
| crdate | date | 是 | 建立日期 | 记录建立日 |

- 使用前分别查询需求日期、上传日期和建立日期的范围，不能混用三者。

## 字典表（关联均已核对）

| 表 | PK | 列与含义 |
|---|---|---|
| uf_cpfl | zcpfl | 产品分类编码 / ztext 产品分类名称 |
| uf_cpxl | zcpxl | 产品小类编码 / ztext 产品小类名称 |
| uf_cpxf | zcpxf | 产品细分编码 / ztext 产品细分名称（含中英文） |
| uf_cpx | 未声明唯一约束，关联前检查重复 | bh 产品线编码 / cpx 产品线名称；varchar(999) |
| uf_jxxl | zjxxl | 机型系列编码 / ztext 机型系列名称（与飞书认证表「机型系列」同源）；zowner 负责人编码（待确认）、zownid 关联ID（待确认）、ZOWNERT 负责人姓名（待确认，需业务确认） |

字典 ztext 为主数据展示用；主表已有 *_TXT 冗余列，一般免 JOIN。

## 常用 JOIN 与坑（结合字典核对结论）

1. **业务表 → 维度**：`JOIN sap_material m ON s.matnr = m.MATNR`（等值，排序规则不区分大小写）。sap_material 部分物料维度缺失或为"其他"，精确分析按 `ZCPXF 非空 AND CPXF_TXT <> N'OTHERS（其他）'` 过滤。
2. **物料号格式**：`150.0045200`、`013.0014600`、`:B710.ZT0012300`、`HY00.0028302` 等前缀风格并存；跨表匹配一律等值 JOIN，不要拼接/截断（尤其业务表 18 位 vs 主表 40 位）。
3. **库存口径**：rd_prd_stock 为月度快照，当前库存 = 最新月末值；**跨月累加无意义**。不同 meins 分组统计。
4. **国家两套口径**：rd_delivery.country（交付国，中文）≠ sap_material.ZGJ（物料国家），不可互作主键或直接对账。
5. **rd_delivery 覆盖可能不全**：使用前探测月份，不作为完整历史出货的替代。
6. **forecast**：zz_oaid 单列不唯一；同单多行按 (zz_oaid, matnr) 统计物料数；bdter 是需求日期。
7. **机型系列字典缺 Z0221**：以 sap_material.JXXL_TXT 冗余列为准兜底。
