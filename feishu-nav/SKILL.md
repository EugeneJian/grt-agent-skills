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

共享 skill 的单一真源为 `~/.agents/skills/`；本 skill 的真实目录是其直接子目录 `feishu-nav/`。真源至少包含一个非隐藏 skill 目录，每个这样的目录均须真实且含 `SKILL.md`；真源和工具目录的路径不得通过软链别名。

- `~/.claude/skills`、`~/.codex/skills` 默认必须有指向每个同名共享 skill 真身的链接，真实副本即使内容相同也不合格
- pi 直接扫描真源，`~/.pi/agent/skills` 可不存在；cc-switch 已退役，`~/.cc-switch/skills` 也可不存在。两者若保留条目，仍检查其归属及链接目标
- 顶层点开头项（如 `.git`、Codex 管理的 `.system`）是元数据边界，排除检查；不要在其中放个人 skill。其他非隐藏工具专属 skill 必须用可重复的 `--tool-specific TOOL:SKILL` 明确声明，名称须是非隐藏的单个目录名，该工具中的实际目录须含 `SKILL.md`，不能与真源或其他工具重名
- `--require-tool TOOL` 可额外要求某个工具完整覆盖共享链接；`--home PATH` 用于隔离测试

```bash
# 只读拓扑审计：安装器更新、新增 skill 或修改链接后运行
python3 ~/.agents/skills/feishu-nav/scripts/skill-ssot-audit.py
```

审计只检测、不修复，也不验证 CLI 安装、认证、飞书权限或各工具实际加载。遇到真实副本/错误链接时停止，先比对并备份，再由本人决定如何处理；不要自动删除、移动或覆盖。新机安装与安全链接步骤见仓库 [README](../README.md)。

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

## 快速全貌协议（项目 / 认证 / 通用多记录表）

目的：降低 TTFT。**默认只给全貌**：字段坐标已预置，直接单次拉取＋本地聚合，禁止先做 field-list 探索；用户追问细节时再展开。

### 通用流程（适用任何多记录业务表）
1. 预置坐标单次 `+record-list`（ndjson 统一落盘到 `~/.agents/skills/.exports/`，先 `mkdir -p`；如 brief.ndjson）
2. 本地聚合：状态分布 → 进行中延期榜 → 卡点主题 top3-5
3. 输出固定骨架：**数据核验行（表名/记录数/最近更新/核验日期）→ 总盘 → 延期榜 → 风险主题 → 「需要展开？」收尾**
4. 同会话已落盘 ndjson 直接复用（在 `~/.agents/skills/.exports/` 下按文件名找）；仅当源表可能已更新（按最近编辑时间或用户声明）才重拉
5. 展开 = 对已落盘数据过滤或补拉缺失字段，不重新探索 schema；默认不向回复倾倒长文本明细

### 项目简报全貌（研发项目）
```bash
mkdir -p ~/.agents/skills/.exports
lark-cli base +record-list --base-token NCcabzBfoa3PofsEgiFcPStKnub \
  --table-id tblOfatmgETxjnvO \
  --field-id fldT5Yrr5O --field-id fld2sCV8DE --field-id fldeUqt2re --field-id fld11bOAiN \
  --field-id fldK4mIbii --field-id fld0c6tXVr --field-id fldQoSDaoS --field-id flduKFQJ8t \
  --field-id fldSyzNO56 --field-id fldGPEPOcu --field-id fldP6jVsu6 --field-id fldZZsdvGo \
  --field-id fldxck8iiZ \
  --format ndjson --output ~/.agents/skills/.exports/brief.ndjson --overwrite --as user
```
字段：项目名称/项目状态/进度状态/当前达成率/部门/里程碑点/里程碑计划与预计完成时间/关键进展/风险点/本周delay原因/资源诉求/认证进展。
- 状态枚举：结案｜进行中｜停滞｜待开案｜取消；进度状态：🟩正常/🟨中度延期/🟥重度延期
- 全貌口径：状态分布 → 进行中×延期榜（计划→预计、达成率）→ 风险主题聚合（软件人力/物料供应链/认证测试资源/需求变更/降本不达标/停滞处置）→ 停滞清单
- 重大事项表 `tbltg9hwmWJYgmxE` 补充：字段 fldvz6qhXF 项目名称/fldKiABzvo 重大亮点暗点/fldSbZQOI5 项目达成率/fldq4jEErR 数据更新时间/fldN9w8EgF 月份；最新完整月 = max(月份)
- 【月.日】无年份：按里程碑与更新时间推断，存疑标注；记录正序/倒序两种都存在，比较日期后取最新；里程碑早已过期且无近期更新的「进行中」标为疑似停更

### 认证总表全貌
```bash
mkdir -p ~/.agents/skills/.exports
lark-cli base +record-list --base-token CWgfbslNmarywBs9LWNc48jln7d \
  --table-id tblfz9QgvNyYxhMK \
  --field-id fldNikiuS4 --field-id fldctBFUvO --field-id fldcpn4qGm --field-id flddKaDmsx \
  --field-id fld6KBWqOq --field-id fldkjijUyQ --field-id fldncpwgkH --field-id fldlsJDvJU \
  --field-id fldNXIJyE6 --field-id fldbceQOyQ --field-id flduJVK9gf --field-id fldwF4KqsS \
  --format ndjson --output ~/.agents/skills/.exports/cert.ndjson --overwrite --as user
```
字段：机型/状态/认证/国家地区/区域/产品线/优先级/认证进程百分比/最新进展记录/重要进展更新日期/研发预计完成日期/实际完成日期。
- 状态枚举：✔️ 完成｜开案/测试/草稿/变更/Unstart/Pending for Clarification（进行中；报价属前置阶段，计入需注明）｜已停滞｜正常/Delay Alert/RoHS（旧值）
- 逾期判定：**研发预计完成日期 < 今天 且实际完成日期为空**；表内 🚨公式（fldHUDrFOR，'1'/'0'）主要命中已停滞旧项，不作为进行中逾期的唯一口径
- 全貌口径：状态分布 → 进行中按区域/产品线 → 逾期榜（>30 天 / 30 天内）→ 卡点主题（测试资源紧缺/草稿确认响应慢/整改失败/新标补测）→ 与项目简报「认证进展」字段交叉验证
- 数据新鲜度：wiki node obj_edit_time 或 max(重要进展更新日期)；部分记录长期无更新需标注停更

