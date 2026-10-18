---
name: feishu-nav
description: 古瑞瓦特个人工作导航与核心项目资源入口（通用 Agent Skill，适配 pi/Claude Code/Codex 等支持 Agent Skills 规范的工具）。当用户提到「导航」「导航表」「我的导航」、要查看/增删导航条目、刷新 Last update，或要查项目简报、能源互联专项简报、研发下单指引、智云产品说明书、Ecology 产品卡片等核心工作表时使用。包含各资源的 token 直达坐标，支持跨会话、跨工具免搜索访问。
compatibility: 需要 Python 3 运行拓扑审计；业务查询需要 lark-cli 已安装、完成 config init，并以用户身份登录（lark-cli auth login --recommend；用 auth status 检查）。飞书文档访问权限跟随账号。
license: MIT
---

# Growatt 个人工作导航

用户（简晓铭，产品经理）的飞书工作资源入口。以下 token/id 为已记录的资源坐标，可跨 session 使用；访问失败或资源迁移时需重新核对原链接。坐标不等于访问凭据，不能绕过账号权限。

## 导航表（主入口）

- URL：https://q02gj5lyidv.feishu.cn/wiki/EOxKwvjQ3igqIdkkdF3cW5SonYn?table=tblgHF305e99kLQz&view=vewrC7NlnR
- base_token：`NNpAbmIera0mI2sVig2csRSbnNb` ｜ table_id：`tblgHF305e99kLQz` ｜ view_id：`vewrC7NlnR`
- 字段：`功能`(text, fldaGujNal) ｜ `类型`(select, fldIULwk2G) ｜ `飞书链接`(text/url, flddwrn60E) ｜ `描述`(text, fldatCEF78) ｜ `版本`(text, fldmHUe5vv) ｜ `Last update`(text, fld21cWyt6)
- 类型选项：信息源 / 知识库 / 看板 / 台账

### 维护约定

- 新增条目：功能 + 类型 + 飞书链接用 `[标题](URL)` 格式；描述写「内容 + 业务」一句话
- Last update 无自动关联（Base 原生不支持读外部文档修改时间），需手动/脚本扫描刷新；写入时用 `drive +search` 或 `+inspect` 取真实 update_time
- 版本字段仅收录自带版本号的文档（如「生态选型表 V08」），在线文档留空

## 关联核心资源（token 直达）

本文件只记录资源坐标，不缓存业务事实（条数、状态、进度、逾期等统计）。**业务信息的权威源（SSOT）是飞书文档/原表**：任何汇报口径必须现查原表取得，并注明核验日期；无法访问或无法复核时须明确说明。

| 资源 | 坐标 |
|---|---|
| 项目简报（研发项目周报） | base `NCcabzBfoa3PofsEgiFcPStKnub` ｜ 表：项目简报 `tblOfatmgETxjnvO`、项目重大事项 `tbltg9hwmWJYgmxE` |
| 认证多维表格（认证总表，机型×认证项目） | base `CWgfbslNmarywBs9LWNc48jln7d`（wiki `XANgwXpdFi5mXykyxcQcY2nWnrg`）｜ 表：认证总表 `tblfz9QgvNyYxhMK`（视图 `vewz5gv2et`） |
| 能源互联专项简报（双周更） | base `EVvvb5diwa4rURsE9K7cCljTnBh` ｜ 表：产品&ECN清单 `tblnPHcI7ND2qsgB` |
| 智云产品资料（说明书索引） | base `PsC8buShJajxp0sPQjncSoahn7g` ｜ 表：产品说明书&操作指南 `tblGmm6MTiOEnHls`、用户协议&隐私政策 `tblLdPGK92z74oe5` |
| 深古研发下单指引链接汇总 | sheet `TBoRsI6vShSQUYthP9YcyfV2nhc`（8 产品线 16 份指引，D 列为文档 mention） |
| Ecology 产品卡片与官方 Source | base `Iwb6bdAuuaiZTEsLslDcoL4pnpe`（表：产品卡片、官方 Source；AI 数据源视图 table=tblqZqBHRFxoOQIQ） |

## SSOT 架构与审计

共享 skill 真源：`~/.agents/skills/`（本 skill 为其直接子目录）。拓扑规则、审计参数与安全约定见 [references/ssot-audit.md](references/ssot-audit.md)。

```bash
# 只读拓扑审计（安装器更新/新增 skill/改链接后运行）
python3 ~/.agents/skills/feishu-nav/scripts/skill-ssot-audit.py
```

## 常用操作

```bash
# 读导航表全部条目（导出统一写入 .exports/：被 Git 忽略，也不参与审计）
mkdir -p ~/.agents/skills/.exports
lark-cli base +record-list --base-token NNpAbmIera0mI2sVig2csRSbnNb \
  --table-id tblgHF305e99kLQz --view-id vewrC7NlnR \
  --field-id fldaGujNal --field-id fldIULwk2G --field-id flddwrn60E --field-id fldatCEF78 --field-id fld21cWyt6 \
  --format ndjson --output ~/.agents/skills/.exports/nav-records.ndjson --overwrite --as user

# 新增/更新条目：+record-batch-create / +record-batch-update（同表串行写入）
```

## 深入文档（按需加载，不要一次性读取）

| 文档 | 何时读 |
|---|---|
| [references/overview-protocol.md](references/overview-protocol.md) | 用户要看项目简报/认证总表全貌，或任何多记录表汇总：预置字段坐标、聚合口径、输出骨架 |
| [references/ssot-audit.md](references/ssot-audit.md) | 审计报错、链接拓扑变更、声明工具专用例外时 |

