# 快速全貌协议（项目 / 认证 / 通用多记录表）

目的：降低 TTFT。**默认只给全貌**：字段坐标已预置，直接单次拉取＋本地聚合，禁止先做 field-list 探索；用户追问细节时再展开。

## 通用流程（适用任何多记录业务表）

1. 预置坐标单次 `+record-list`（ndjson 统一落盘到 `~/.agents/skills/.exports/`，先 `mkdir -p`；如 brief.ndjson）
2. 本地聚合：状态分布 → 进行中延期榜 → 卡点主题 top3-5
3. 输出固定骨架：**数据核验行（表名/记录数/最近更新/核验日期）→ 总盘 → 延期榜 → 风险主题 → 「需要展开？」收尾**
4. 同会话已落盘 ndjson 直接复用（在 `~/.agents/skills/.exports/` 下按文件名找）；仅当源表可能已更新（按最近编辑时间或用户声明）才重拉
5. 展开 = 对已落盘数据过滤或补拉缺失字段，不重新探索 schema；默认不向回复倾倒长文本明细

## 项目简报全貌（研发项目）

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

## 认证总表全貌

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
