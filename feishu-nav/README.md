# feishu-nav · Growatt 个人工作导航 Skill

古瑞瓦特个人工作导航与核心项目资源入口，适配 pi / Claude Code / Codex 等支持 Agent Skills 规范的工具。

## 📦 GitHub 地址

- 仓库：https://github.com/EugeneJian/grt-agent-skills
- 本 skill 目录：https://github.com/EugeneJian/grt-agent-skills/tree/main/feishu-nav
- 安装部署（新机同步、SSOT 软链架构）：见[仓库 README](../README.md)

## 🧭 这是什么

用户（简晓铭，产品经理）的飞书工作资源导航，维护在一张多维表格「导航」中：

- 入口：https://q02gj5lyidv.feishu.cn/wiki/EOxKwvjQ3igqIdkkdF3cW5SonYn?table=tblgHF305e99kLQz&view=vewrC7NlnR
- base_token `NNpAbmIera0mI2sVig2csRSbnNb` ｜ table_id `tblgHF305e99kLQz` ｜ view_id `vewrC7NlnR`
- 字段：`功能` ｜ `类型`（信息源/知识库/看板/台账） ｜ `飞书链接` ｜ `描述` ｜ `版本` ｜ `Last update`

skill 内预置了各核心资源（项目简报、认证多维表格、能源互联专项简报、智云产品资料、研发下单指引、Ecology 产品卡片等）的 token 直达坐标，可跨会话、跨工具免搜索访问。完整坐标与业务口径见 [SKILL.md](SKILL.md)。

## 📖 使用说明

### 触发方式

无需专门命令。对 AI 助手自然语言提到「导航」「导航表」「我的导航」，或要查看/增删导航条目、刷新 Last update，或要查项目简报、能源互联专项简报、研发下单指引、智云产品说明书、Ecology 产品卡片等核心工作表时，skill 自动生效。

### 前置条件

- Python 3（拓扑审计脚本需要）
- `lark-cli` 已安装并完成 `config init`，以用户身份登录（`lark-cli auth login --recommend`，用 `lark-cli auth status` 检查）
- 飞书文档访问权限跟随账号

### 常用操作

**1. 查看导航表全部条目**

```bash
mkdir -p ~/.agents/skills/.exports
lark-cli base +record-list --base-token NNpAbmIera0mI2sVig2csRSbnNb \
  --table-id tblgHF305e99kLQz --view-id vewrC7NlnR \
  --field-id fldaGujNal --field-id fldIULwk2G --field-id flddwrn60E --field-id fldatCEF78 --field-id fld21cWyt6 \
  --format ndjson --output ~/.agents/skills/.exports/nav-records.ndjson --overwrite --as user
```

**2. 新增 / 更新导航条目**

用 `lark-cli base +record-batch-create` / `+record-batch-update`（同表串行写入）。维护约定：

- 功能 + 类型 + 飞书链接用 `[标题](URL)` 格式；描述写「内容 + 业务」一句话
- Last update 无自动关联，手动刷新时用 `drive +search` 或 `+inspect` 取真实 update_time 再写入
- 版本字段仅收录自带版本号的文档，在线文档留空

**3. 核心业务表快速全貌**

项目简报 / 认证总表等已预置字段坐标，单次 `+record-list` 落盘 ndjson 后本地聚合，输出「数据核验行 → 总盘 → 延期榜 → 风险主题」骨架；完整协议与命令见 [SKILL.md](SKILL.md) 的「快速全貌协议」章节。

**4. SSOT 拓扑审计**

安装器更新、新增 skill 或修改链接后运行（只读检测，不修复）：

```bash
python3 ~/.agents/skills/feishu-nav/scripts/skill-ssot-audit.py
```

新机安装与软链建立用 `scripts/setup-tool-links.py`，步骤见[仓库 README](../README.md)。

### 注意事项

- 坐标不等于访问凭据，不能绕过账号权限；访问失败或资源迁移时需重新核对原链接
- SKILL.md 中的历史业务快照不会自动更新，用于新汇报前必须重读原始表格核对并注明核验日期
- 导出文件统一写入 `~/.agents/skills/.exports/`（被 Git 忽略，也不参与审计）

## 📄 目录结构

```text
feishu-nav/
├── README.md            ← 本说明文档
├── SKILL.md             ← Agent Skill 主文件（坐标、口径、协议）
├── scripts/
│   ├── skill-ssot-audit.py    # 只读拓扑审计
│   └── setup-tool-links.py    # 新机工具软链建立
└── tests/
    └── test_skill_ssot_audit.py
```

License：MIT
