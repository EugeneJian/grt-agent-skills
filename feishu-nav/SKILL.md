---
name: feishu-nav
description: 古瑞瓦特个人工作导航与核心项目资源入口（通用 Agent Skill，适配 pi/Claude Code/Codex 等支持 Agent Skills 规范的工具）。当用户提到「导航」「导航表」「我的导航」、要查看/增删导航条目、刷新 Last update，或要查项目简报、能源互联专项简报、研发下单指引、智云产品说明书、Ecology 产品卡片、Ecology 生命周期阶段与资源（五阶段活动及工具/数据源目录）等核心工作表时使用。包含各资源的 token 直达坐标，支持跨会话、跨工具免搜索访问。
compatibility: 需要 Python 3 运行拓扑审计；业务查询需要 lark-cli 已安装、完成 config init，并以用户身份登录（lark-cli auth login --recommend；用 auth status 检查）。飞书文档访问权限跟随账号。
license: MIT
---

# Growatt 个人工作导航

> 面向人类阅读的说明文档（含 GitHub 地址、部署与使用说明）见 [README.md](README.md)；本文件面向 Agent 消费。

用户（简晓铭，产品经理）的飞书工作资源入口。以下 token/id 为已记录的资源坐标，可跨 session 使用；访问失败或资源迁移时需重新核对原链接。坐标不等于访问凭据，不能绕过账号权限。

## 仅载入、尚无具体任务时

当用户仅显式点名或载入本 Skill，且本轮与上下文都没有待执行的具体任务时，先简短说明本 Skill 已支持的能力，给出少量请求示例，并邀请用户说明目标。此时基于本文件回复，不运行命令、连接服务或读取业务数据。

用户已给出具体任务，或上下文有仍待执行的任务时，直接按任务处理。自动发现 Skill、或为完成已有任务读取本文件，不触发这段介绍。

开场示例（可按场景精简）：

> 我可以帮你查看和维护工作导航，定位项目简报、认证、下单指引与产品资料，并按原始资源核对字段和更新信息。你可以说：“看看我的导航”“汇总项目简报”“核对认证总表的字段映射”。直接告诉我目标即可。

## 导航表（主入口）

- URL：https://q02gj5lyidv.feishu.cn/wiki/EOxKwvjQ3igqIdkkdF3cW5SonYn?table=tblgHF305e99kLQz&view=vewrC7NlnR
- base_token：`NNpAbmIera0mI2sVig2csRSbnNb` ｜ table_id：`tblgHF305e99kLQz` ｜ view_id：`vewrC7NlnR`
- 字段：`功能`(text, fldaGujNal) ｜ `类型`(select, fldIULwk2G) ｜ `飞书链接`(text/url, flddwrn60E) ｜ `描述`(text, fldatCEF78) ｜ `Agent 指引`(text, fldxPMJC4o) ｜ `版本`(text, fldmHUe5vv) ｜ `Last update`(text, fld21cWyt6)
- 类型选项：信息源 / 知识库 / 看板 / 台账 / 外部链接
- **本 skill 涉及资源的领域 SSOT 声明维护在各条目的`描述`字段中**（如「产品生命周期以 Ecology 产品卡片为准」）：读取对应业务前先读导航，定位并核验原表；与已有权威源声明冲突时明确指出，不凭导航描述覆盖。导航修改在下次读取时生效，无需改 skill
- **单资源操作协议（字段坐标、状态枚举、聚合口径、交叉验证规则）维护在各条目的`Agent 指引`字段**：处理该资源前先读对应条目指引，复用有效坐标直接拉取，不做例行 field-list 探索；指引缺失、字段映射冲突或查询报错时，仅对受影响的字段/表做只读核验。不能仅凭字段非空认定迁移完整；通用流程与异常处理见 [references/overview-protocol.md](references/overview-protocol.md)

### 维护约定

- 新增条目：功能 + 类型 + 飞书链接用 `[标题](URL)` 格式；描述写「内容 + 业务」一句话；有操作协议的资源同步写 `Agent 指引`（字段坐标/口径）
- Last update 无自动关联（Base 原生不支持读外部文档修改时间），需手动/脚本扫描刷新；写入时用 `drive +search` 或 `+inspect` 取真实 update_time（wiki 链接可用 `wiki +node-get` 的 obj_edit_time 比对）
- 版本字段仅收录自带版本号的文档（如「生态选型表 V08」），在线文档留空
- 领域 SSOT 声明的维护点是导航条目描述；单资源操作协议的维护点是导航条目「Agent 指引」。本 skill 保留导航读取流程与资源坐标，不另存一份单资源协议；核验发现的缺失/冲突应明确报告，修改导航仍需对应写入授权

## 关联核心资源（token 直达）

本文件只记录资源坐标，不缓存业务事实（条数、状态、进度、逾期等统计）。**业务信息的权威源（SSOT）是飞书文档/原表**：任何汇报口径必须现查原表取得，并注明核验日期；无法访问或无法复核时须明确说明。

| 资源 | 坐标 |
|---|---|
| 项目简报（研发项目周报） | base `NCcabzBfoa3PofsEgiFcPStKnub` ｜ 表：项目简报 `tblOfatmgETxjnvO`、项目重大事项 `tbltg9hwmWJYgmxE` |
| 认证多维表格（认证总表，机型×认证项目） | base `CWgfbslNmarywBs9LWNc48jln7d`（wiki `XANgwXpdFi5mXykyxcQcY2nWnrg`）｜ 表：认证总表 `tblfz9QgvNyYxhMK`（视图 `vewz5gv2et`） |
| 能源互联专项简报（双周更） | base `EVvvb5diwa4rURsE9K7cCljTnBh` ｜ 表：产品&ECN清单 `tblnPHcI7ND2qsgB` |
| 智云产品资料（说明书索引） | base `PsC8buShJajxp0sPQjncSoahn7g` ｜ 表：产品说明书&操作指南 `tblGmm6MTiOEnHls`、用户协议&隐私政策 `tblLdPGK92z74oe5` |
| 深古研发下单指引链接汇总 | sheet `TBoRsI6vShSQUYthP9YcyfV2nhc`（8 产品线 16 份指引，D 列为文档 mention） |
| Ecology 产品卡片与官方 Source | base `Iwb6bdAuuaiZTEsLslDcoL4pnpe` ｜ 产品卡片 `tblqZqBHRFxoOQIQ`（`生命周期` fldO4GeSSS）｜ 官方 Source `tblD8ivGCAGfNQDJ`（AI 数据源，视图 `vewV9cM8xs`） |
| Ecology 生命周期阶段与资源 | base `SajBbNOpDaMwpSsK0yUcdr6Ence` ｜ 阶段工作清单 `tbl7GlArW31ZLngO`（五阶段总览 `vewMsyuTsP`、阶段看板 `vewx8yUYLC`）｜ 工具与数据源 `tblfTCKa0ox8Rx0G`（资源总览 `vewYMdMi6Q`） ｜ 导航条目 `reczz28PzJhSU4pz` |

读取或维护「Ecology 生命周期阶段与资源」时，先读导航同名条目的最新「Agent 指引」，取得字段映射、阶段视图与关联规则。活动模板、资源目录及其关联直接在线维护；真实产品生命周期、项目进度、审批与业务事实继续按原始来源核验。

## SSOT 架构与审计

共享 skill 真源：`~/.agents/skills/`（本 skill 为其直接子目录）。拓扑规则、审计参数与安全约定见 [references/ssot-audit.md](references/ssot-audit.md)。

```bash
# 只读拓扑审计（安装器更新/新增 skill/改链接后运行）
python3 ~/.agents/skills/feishu-nav/scripts/skill-ssot-audit.py
```

## 常用操作

```bash
# 读导航视图条目（导出统一写入 .exports/；CLI 的 --output 仅接受当前目录下的相对路径）
mkdir -p ~/.agents/skills/.exports
cd ~/.agents/skills/.exports
lark-cli base +record-list --base-token NNpAbmIera0mI2sVig2csRSbnNb \
  --table-id tblgHF305e99kLQz --view-id vewrC7NlnR \
  --field-id fldaGujNal --field-id fldIULwk2G --field-id flddwrn60E --field-id fldatCEF78 --field-id fldxPMJC4o --field-id fld21cWyt6 \
  --format ndjson --output ./nav-records.ndjson --overwrite --as user

# 新增/更新条目：+record-batch-create / +record-batch-update（同表串行写入）
```

## 深入文档（按需加载，不要一次性读取）

| 文档 | 何时读 |
|---|---|
| [references/overview-protocol.md](references/overview-protocol.md) | 用户要看任何多记录表全貌：通用拉取/聚合/输出骨架；单资源协议（字段坐标与口径）在导航「Agent 指引」 |
| [references/ssot-audit.md](references/ssot-audit.md) | 审计报错、链接拓扑变更、声明工具专用例外时 |

