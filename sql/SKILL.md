---
name: sql
description: 只读分析公司 SAP 物料、库存、预测和历史出货。默认查询内网 oa_report SQL Server，历史出货入口为 rd_delivery 月度汇总；rd_delivery 为出货 SSOT 目标，结构升级前维持旧表查询；本机与 Supabase 为验证或查询副本。用于 sap_material、PN 关联、产品线出货和供需分析。
---

# 公司业务数据只读查询

适用于 Pi、Claude Code、Codex 等能执行 Python 的 Agent。默认使用 `intranet`（内网 SQL Server），通过统一查询脚本访问 `rd_delivery` 与实时 `sap_material`。本机 PostgreSQL 的 `local` 保留用于同步验证；运行配置和凭据由所在环境提供，不依赖特定客户端的 MCP。

出货权威目标已指定为 `oa_report.dbo.rd_delivery`，物料权威源仍为 `sap_material`。当前结构升级与历史验收尚未完成，保持 `report_only`。PostgreSQL 历史仅作一次性迁移输入；切换后本机与 Supabase 均由内网已提交版本发布。 规则见 [出货 SSOT](references/rd-delivery-ssot.md)。

## 仅载入、尚无具体任务时

当用户仅显式点名或载入本 Skill，且本轮与上下文都没有待执行的具体任务时，先简短说明本 Skill 已支持的能力，给出少量请求示例，并邀请用户说明目标。此时基于本文件回复，不运行命令、连接服务或读取业务数据。

用户已给出具体任务，或上下文有仍待执行的任务时，直接按任务处理。自动发现 Skill、或为完成已有任务读取本文件，不触发这段介绍。

开场示例（可按场景精简）：

> 我可以只读查询物料、库存、预测和历史出货，分析产品线或国家趋势、关联完整 PN，并核对本机与云端查询结果。你可以说：“查某个 PN 的最新库存”“分析上个月各产品线出货”“核对本机与云端出货结果”。直接告诉我目标即可。

## 选择数据源

| 问题 | 入口 |
|---|---|
| 出货月度趋势、PN / 国家下钻 | 默认 `intranet`，运行 `scripts/query_data.py`；先读 [内网交货口径](references/intranet-delivery.md) |
| 物料、PN 属性 | 默认 `intranet`，`material` 直接查询实时 SSOT |
| 完整来源明细、原统计口径核对 | 显式 `local`；云端使用显式 `cloud`，先核对覆盖 |
| 同步后核对本机与云端 | 显式使用 `local`，或 `compare_profiles.py --left local --right cloud` |
| 实时物料 SSOT、库存、预测、指定 `rd_delivery` | 原 `scripts/query.py`，仅 SQL Server；读 [源库说明](references/schema.md) 和 [查询模式](references/query-patterns.md) |
| 出货与库存 / 预测关联 | 两处分别按完整 PN、期间、单位聚合，再在分析环境关联 |

产品线 → 机型系列是默认下钻路径；铭牌型号、功率和 PN 按需展开，国家与时间为独立轴。具体字段、未知值保留和两阶段铭牌关联统一遵循 [出货语义](references/shipping-analysis.md#维度与下钻语义唯一业务口径)，不要把 CPXH 产品型号当作 ZMODEL 铭牌型号。

## 通用出货查询

`<skill_dir>` 为读取本文件所在目录。Python 3.9+；内网 SQL Server 需要 `pymssql`，PostgreSQL 需要 `psql`，HTTPS 使用 Python 标准库。

```bash
python3 <skill_dir>/scripts/query_data.py --list-profiles
python3 <skill_dir>/scripts/query_data.py @查询.json
python3 <skill_dir>/scripts/query_data.py --profile local @查询.json
python3 <skill_dir>/scripts/compare_profiles.py --left local --right cloud @查询.json
```

查询 JSON 使用统一的字段、筛选和分页；各通道的数据粒度和已发布数据集不同，不能假定可以互换。配置默认读取 `~/.config/company-sql/profiles.json`，可用 `COMPANY_SQL_CONFIG` 或 `--config` 指定。标准配置的 `default_profile` 为 `intranet`，省略 `--profile` 即访问内网 SQL Server。`local` 用于来源核对，`cloud` 保留为显式可选入口；不自动回退。其他电脑配置自己的内网凭据，Skill 不携带密码或员工会话。

另一台电脑从 GitHub 安装或更新，读 [多机同步与登录](references/new-computer.md)：优先配置内网连接；需要云端时再初始化并由本人登录，不复制旧电脑的 Auth 会话。首次接入失败，读 [连接与部署](references/connections.md)。编写查询时读 [查询约定](references/query-contract.md)，字段白名单见 [datasets.json](references/datasets.json)。脚本接受查询 JSON，不接受任意 SQL；返回 JSON 中的 `has_more` 为 true 时必须继续分页，不能把第一页当作完整统计。

完整来源 / 云端例子（须显式选择 `local` / `cloud`，不能假定内网已覆盖）：[2026 年 9 月全部产品线及单位](references/september-2026-all-lines.json)。截图专项校验使用 [九月十条线](references/september-2026.json) 或 [1–9 月十条线](references/january-september-2026.json)。普通出货问题使用完整范围，不能自动沿用截图的十条线名单；按用户问题改期间和范围。

默认统计不含机壳（Z0090），保留所有国家。`rd_delivery` 只有月度汇总，不保留日级来源行和单位；未验证的单位返回 `UNSPECIFIED`，不得称为 PCS 或与已知单位合并。完整来源通道保留原来源行，数量按销售单位分别汇总。含机壳仅在用户要求时使用 `*_including_housing` 数据集。PN 用完整文本，禁止转数字、去前导零或截断。结果中说明期间、单位、机壳口径及数据截止 / 同步时间。

内网或云端连接失败、请求期间不在覆盖范围时明确报告，不能推断为零出货，也不能自动切换通道。不要拼加两处同源出货。用户明确指定其他通道或要求同步核对时，再切换并说明所用通道和副本新鲜度。

## 实时 SQL Server 查询

源库为内网 `oa_report` SQL Server；实际主机和端口由所在环境的 `OA_HOST/OA_PORT` 提供。原封装脚本及凭据加载方式保留：

```bash
python3 <skill_dir>/scripts/query.py @查询.sql
```

依赖 `pymssql`。凭据由部署环境的 `OA_HOST/OA_PORT/OA_USER/OA_PWD/OA_DB` 提供，也兼容本机 Skill 根目录既有 `.env`。共享 Skill 包不分发 `.env`。只运行单条 `SELECT` / 只读 `WITH`；脚本有词法校验，日常部署应由 IT 提供只读账号；现有维护账号虽有写权限，本查询入口仍只生成固定 SELECT，不借此执行写入。

`sap_material` 是物料 SSOT；`rd_prd_stock` 是月度库存快照，跨月不可相加；`rd_forecast` 是需求预测；`rd_delivery` 是默认内网月度入口，但不代表完整历史出货。查询前探测最新年月，不固定使用旧快照。物料状态 / OTHERS 等库存分析筛选不能自动套到历史出货。

## 权限与凭据

新增出货文件入库、失败批次续传及双端同步使用同仓库的 `shipment-maintenance` Skill；未安装时报告缺少维护入口。本 Skill 的查询脚本仍只读，不代替维护流程。

本 Skill 仅查询，不执行同步、迁移或数据库写入。PostgreSQL 使用专用只读身份；云端使用 publishable / 兼容 anon 项目 Key 加员工访问 JWT，授权由服务端控制。凭据放环境变量或公司密钥管理，不写进 Skill、查询文件或回复。不得借用其他 Agent 的 OAuth 凭据，禁止使用管理员 / service_role Key 充当日常查询身份。

云端也支持 profile 指定 Skill 外部的 `credentials_file`（0600）：读取独立授权身份的会话并自动刷新。已有 Auth 账号可用 `scripts/auth_login.py` 在终端交互登录，密码不落盘；配置和登录方式见连接说明。登录或续期不等于获得业务数据权限。

点击邮件的浏览器登录可用 `scripts/auth_callback.py` 接收本机回调；收到 localhost 拒绝连接时先检查接收器。会话和邮件链接不应粘贴到聊天。已建立的会话由共享客户端自动续期，各 Agent 日常查询无需重新登录。

已有只读 MCP 可作为额外入口；它不是本 Skill 的运行依赖，也不会因为读取本文件自动获得连接。

