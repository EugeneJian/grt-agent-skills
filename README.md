# GRT Agent Skills · 同步与 SSOT 部署指南

团队 skill 的多机同步与分发方案。共享 skill 的唯一真源（SSOT）是 `~/.agents/skills/`；Git 同步本仓库纳管的 skill（`feishu-nav`、`sql`、`shipment-maintenance`、`feishu-lark`），安装器独立管理 CLI 本体等其他第三方内容。

## 架构

```text
~/.agents/skills/                         ← 共享 skill 的真实目录
├── feishu-nav/                           ← 本 Git 仓库纳管
│   ├── SKILL.md
│   ├── scripts/                            ← SSOT 审计 + 工具链接预检脚本
│   └── tests/
├── sql/                                 ← 本 Git 仓库纳管
│   ├── SKILL.md
│   ├── references/schema.md
│   ├── scripts/query.py                   ← 内网 SQL Server 只读查询
│   └── tests/
├── feishu-lark/                          ← 本 Git 仓库纳管（lark-cli 包装 skill）
│   └── SKILL.md                          （lark-cli CLI 本体由 npm 单独安装）
└── claude-code-toolsearch/               ← 本 Git 仓库纳管（Claude Code 排障常识）
    └── SKILL.md                          （仅 Claude Code 适用，不分发给其他 agent）

~/.agents/skills/.skill-tools             ← 工具分发清单（隐藏文件，Git 纳管）
~/.claude/skills/<共享 skill 名>           → 对应真源目录（按分发清单，必需）
~/.codex/skills/<共享 skill 名>            → 对应真源目录（按分发清单，必需）
~/.codex/skills/.system/                  ← Codex 管理的内置例外
~/.pi/agent/skills/                       ← 可不建；pi 直接扫描真源
~/.cc-switch/skills/                      ← 已退役、可不建
```

- 共享 skill 必须是规范目录的非隐藏直接子目录，含 `SKILL.md`，不能再是软链
- **渐进式披露约定**：`SKILL.md` 只保留入口层（定位、能力地图、主坐标、深入文档索引），建议 ≤100 行；查询协议、字段口径、审计规则等深水内容放 `<skill>/references/*.md`，agent 按任务需要再读取。新增深度内容时优先扩 references，不要把 SKILL.md 养成大全
- Claude/Codex 的同名条目必须是指向该 skill 真身的软链，不能复制一份
- **工具分发**：根目录 `.skill-tools` 按 skill 声明分发工具（claude、codex、pi=扫描真源可见），未声明的默认全部；对 pi 隐藏的需同时在忽略链路补规则，预检与审计都会校验（如 claude-code-toolsearch 仅分发 claude）
- pi、cc-switch 的目录或链接缺失允许；若存在条目，同样检查其归属和链接目标
- Codex 的 `.system` 由工具管理。其他非隐藏的工具专属 skill 需逐项声明，见下文
- 审计仅覆盖顶层非隐藏 skill 条目；`.git`、`.system` 等点开头的元数据项排除检查，不验证其内容，也不支持把任何 skill 藏在这些目录中

两条维护通道独立执行，不自动拉取、推送或迁移：

| 通道 | 内容 | 方式 |
|---|---|---|
| Git | `feishu-nav`、`sql`、`shipment-maintenance`、`feishu-lark`、`claude-code-toolsearch`、README、忽略规则与 `.skill-tools` 分发清单 | 公开仓库 `EugeneJian/grt-agent-skills`（面向 Growatt 团队分发） |
| 安装器 | `lark-cli` CLI 本体及其他第三方 skill | 按各自官方安装/更新说明维护，不提交到本仓库 |

## 新电脑部署

以下命令面向 macOS/Linux 终端；Windows 差异见本节末尾「Windows 系统差异说明」。已有环境请先盘点；不要直接复制整段执行，也不要删除或覆盖已有目录。

### 1. 准备命令行工具

从各工具官方渠道安装 Node.js（含 npm/npx）、Git、GitHub CLI（`gh`）和 Python 3，然后确认它们可用：

```bash
node --version
npm --version
npx --version
git --version
gh --version
python3 --version
gh auth status
```

Windows 可用 winget 一并安装：`winget install OpenJS.NodeJS.LTS Git.Git GitHub.cli Python.Python.3.12`（Python 安装时勾选「Add python.exe to PATH」；Windows 上命令是 `python`，详见「Windows 系统差异说明」）。

GitHub 未登录时，由本人执行 `gh auth login`，选择自己的账号（clone 公开仓库不需要登录，推送仍需认证）。不要将登录凭据放入仓库。

### 2. 安放团队 skill 仓库

先只读检查目标位置：

```bash
python3 - <<'PY'
from pathlib import Path
p = Path.home().resolve() / ".agents" / "skills"
if (p.parent.is_symlink() or (p.parent.exists() and not p.parent.is_dir())
        or p.is_symlink() or (p.exists() and (not p.is_dir() or any(p.iterdir())))):
    raise SystemExit(f"停止：{p} 已有内容或不是普通目录，请先人工盘点；未做任何修改")
print(f"可用于新克隆：{p}（当前不存在或为空目录）")
PY
```

仅在检查通过后克隆：

```bash
git clone https://github.com/EugeneJian/grt-agent-skills.git "$HOME/.agents/skills"
```

**如果目录已经非空：停止新机克隆流程。** 若它已是本仓库，检查 `git -C ~/.agents/skills remote -v` 和 `git -C ~/.agents/skills status` 后转到日常维护；若不是，先逐项核对来源、内容差异并另行备份，由本人决定如何合并。不要自动 `rm`、`mv`、重新初始化 Git 或强制覆盖。此指南和审计脚本都不执行迁移。

### 3. 安装 lark-cli 与 feishu-lark skill（飞书操作的关键依赖）

`feishu-lark` 是操作飞书的关键 skill：agent 借助它调用 `lark-cli`，完成云文档、多维表格、消息、日历等全部飞书操作。它分两部分，缺一不可：

1. **skill 文件**（`feishu-lark/SKILL.md`）：已随本仓库分发，clone 即得，含 agent 路由与用法说明
2. **`lark-cli` 命令行**：npm 包 `@larksuite/cli`，需每台机器单独安装、配置并登录

依据 [lark-cli 官方安装说明](https://github.com/larksuite/cli/blob/main/README.zh.md)（核对于 2026-10-18），人类用户的安装与配置步骤是：

```bash
npx @larksuite/cli@latest install     # 安装 CLI
command -v lark-cli                   # 确认在 PATH 上（找不到时按安装器提示检查 PATH）
lark-cli config init                  # 交互式配置应用凭证（仅一次，本人完成）
lark-cli auth login --recommend       # 本人授权登录，确认所授权的权限
lark-cli auth status                  # 确认认证有效
```

每步成功后再继续；认证失败时先处理认证，不要把拓扑审计通过当作修复。安装后重新打开会话，确认各工具能加载 `feishu-lark`，再执行一次只读操作验证（如 `lark-cli skills list`）。

**可选：官方领域 skill 目录。** `feishu-lark` 包装 skill 在运行时通过 `lark-cli skills list / skills read` 加载 CLI 内嵌的领域 skill，无需额外安装。如偏好把领域 skill 装成本地目录（如 `lark-doc/`、`lark-base/` 等），可按官方说明执行 `npx skills add larksuite/cli -g -y`。安装后检查实际落盘位置，不能假设安装器总会生成本仓库要求的布局；发现工具目录中的真实副本时，先停下、比较并备份，再人工决定处理方式。其他第三方 skill 仍由各自安装器维护，不入库。

### 4. 预检并补齐共享 skill 的链接

预检脚本已随仓库提供（`feishu-nav/scripts/setup-tool-links.py`，逻辑与下述规则一致）：**默认只读**，检查完全部目标才打印计划，不会删除、移动或替换任何东西。已有真实 skill 目录、普通文件、错误/断裂链接会让它停止；工具根目录及其父目录是软链时也停止。先人工处理这些冲突，再重新预检。

确认计划后才加 `--apply`，此时才创建缺失的 Claude/Codex 目录与链接。已正确的链接保持原样。不要用 `ln -sfn` 覆盖已有目录，它可能把新链接建到目录内部；Windows 不要用 `mklink /J`（junction 不被审计接受），统一运行本脚本。

```bash
python3 ~/.agents/skills/feishu-nav/scripts/setup-tool-links.py            # 只读预检
python3 ~/.agents/skills/feishu-nav/scripts/setup-tool-links.py --apply    # 确认计划后才创建
```

该步骤只补齐共享链接，不整理其他现有条目。运行期间不要同时运行其他安装器；若创建中途因权限等错误停止，已创建的链接保留，排除原因后可再次预检并补齐。

### 5. 分别验证布局、认证和工具加载

```bash
python3 ~/.agents/skills/feishu-nav/scripts/skill-ssot-audit.py
lark-cli auth status
```

审计通过只代表目录布局符合下述规则，**不代表 CLI 安装、飞书权限、业务命令或各工具实际加载已验证**。重新打开相关工具的会话，通过各自的 skill 列表/调用入口确认能加载 `feishu-nav`，再对有权访问的导航表做一次只读查询。

### Windows 系统差异说明（公司主要环境）

公司内多数同事使用 Windows（Windows 10/11 + PowerShell）。以下差异适用于本节全部步骤：

> ⚠️ **本节尚未在真实 Windows 机器上实测验证**（撰写于 macOS 环境，依据各工具官方文档整理）。首次在 Windows 部署时如遇命令或行为差异，请核对官方文档并反馈修正本节。

1. **终端与权限**：使用 PowerShell。创建符号链接前先开启「开发者模式」（设置 → 系统 → 开发者选项 → 开发人员模式），或以管理员身份运行 PowerShell；否则 `setup-tool-links.py --apply` 会因权限失败。目录 junction 不符合 SSOT 审计要求（会被判为真实副本），不要用 `mklink /J` 替代。
2. **路径**：`~/.agents/skills` 即 `%USERPROFILE%\.agents\skills`（PowerShell 写作 `$HOME\.agents\skills`）。
3. **Python**：从 python.org 安装并勾选「Add python.exe to PATH」；Windows 上命令是 `python`（或 `py`），上文所有 `python3` 替换为 `python`。
4. **工具安装**：`winget install OpenJS.NodeJS.LTS Git.Git GitHub.cli Python.Python.3.12`；Git 克隆、`gh auth login`、lark-cli 各命令与上文一致（lark-cli 安装后若找不到命令，按安装器输出检查 PATH）。
5. **第 2 步克隆前检查**：PowerShell 用 `Test-Path $HOME\.agents\skills`；已存在且非空时同样停止并人工盘点，不要覆盖。
6. **第 3 步 .env**：用 `notepad $HOME\.agents\skills\sql\.env` 创建（保存时文件名写作 `".env"`，避免变成 `.env.txt`）；pymssql 装法 `python -m pip install pymssql`。
7. **第 4/5 步脚本**：`python $HOME\.agents\skills\feishu-nav\scripts\setup-tool-links.py`（先预检后 `--apply`，需开发者模式或管理员）、`python $HOME\.agents\skills\feishu-nav\scripts\skill-ssot-audit.py`。
8. **Git Bash**：可用来执行上文 bash 命令，但**链接创建不要在 Git Bash 里做**（其 `ln -s` 默认生成副本而非真软链），统一用上面的 Python 脚本。

## SQL Skill：内网默认与可选云端

默认查询内网 SQL Server 的 `rd_delivery` 月度表和实时 `sap_material`，安装 `pymssql` 并在各电脑安全配置 OA 连接。旧表覆盖与单位须核对，完整来源仍可显式查询本机 PostgreSQL。Supabase HTTPS 改为可选入口。GitHub 只同步 Skill 文件，各电脑的连接配置和员工会话留在仓库外。新电脑下载完整 `sql/` 后，先读 [内网交货口径](sql/references/intranet-delivery.md)；需要云端时再按 [多机同步与登录](sql/references/new-computer.md) 初始化并用本人邮箱登录；已有电脑更新 Skill 时保留自己的会话。HTTPS 入口仅需 Python 3.9+，不需要复制本机 PostgreSQL 或配置 MCP。

出货权威目标已指定为 `oa_report.dbo.rd_delivery`，物料权威源仍为 `sap_material`。当前结构升级与历史验收尚未完成，保持 `report_only`。PostgreSQL 历史仅作一次性迁移输入；切换后本机与 Supabase 均由内网已提交版本发布。 详见 [SSOT 规则](sql/references/rd-delivery-ssot.md)。

## 出货 Excel 增量维护

新增文件入库使用独立 [shipment-maintenance Skill](shipment-maintenance/SKILL.md)：当前内网默认 `report_only`，先生成本机与 `rd_delivery` 差异报告，不写库。另行获批且已部署的云端模式才执行本机预演、提交、同步与归档。日常 `sql` 继续只读。维护需管理员一次性部署固定 RPC 并单独授权员工；没有配置时明确报告未接通。配置、Excel、批次、业务报告与会话不入 Git。具体安装见 [维护部署说明](shipment-maintenance/references/setup.md)。

## 日常维护

1. 每台机器在开始编辑前，先检查工作区，再拉取。若有未提交工作，先审阅并妥善保存，不能继续照抄后续命令：

   ```bash
   cd "$HOME/.agents/skills"
   git status --short
   # 仅在工作区干净时继续；失败就停止
   git pull --ff-only
   ```

2. `pull --ff-only` 因分叉、冲突或其他原因失败时停止编辑/推送，先检查 `git status` 和提交历史，备份本地工作并人工决定如何整合。不要自动 rebase、强制 push、`reset --hard` 或 `git clean`。
3. 编辑 skill 内容后，逐步检查并提交；任一步失败都先处理，不要继续：

   ```bash
   python3 -m unittest discover -s feishu-nav/tests -v
   python3 -m unittest discover -s sql/tests -v
   git diff --check
   git diff -- README.md .gitignore feishu-nav/ feishu-lark/ sql/
   # 人工确认无凭据、导出业务数据或无关变更后再暂存
   git add README.md .gitignore feishu-nav/ feishu-lark/ sql/
   git diff --cached --check
   git diff --cached
   # 再次确认暂存内容后
   git commit -m "更新 skill"
   git push
   ```

4. 其他电脑在本地工作区干净时同样运行 `git pull --ff-only`。推送因远端有新提交而被拒绝时，停止并按第 2 步人工处理，不要强推。若拉到的提交重命名了 skill，另见下节「重命名迁移」。
5. 更新/新装第三方 skill 后，重新做链接预检并运行拓扑审计。安装器更新与 Git 同步互不替代。

## 重命名迁移（多台电脑）

仓库内的 skill 重命名（如 `oa-report → sql`、`growatt-nav → feishu-nav`）后，其他电脑**只 `git pull` 不会自动迁移链接**：旧名软链仍指向已改名的真源路径（变成断链），新名链接也不存在。每台电脑拉取到重命名提交后，按以下顺序人工处理；任何一步与预期不符就停下盘点，不要批量删除：

```bash
# 1) 拉取后先看审计结果；预期会报旧链接断链/错误目标、新链接缺失入口
cd "$HOME/.agents/skills" && git pull --ff-only
python3 ~/.agents/skills/feishu-nav/scripts/skill-ssot-audit.py

# 2) 只读盘点两个工具目录的链接现状
ls -l ~/.claude/skills ~/.codex/skills

# 3) 人工确认旧名条目是指向 ~/.agents/skills/<旧名> 的软链、且真源确已改名后，
#    仅删除这些软链本身（rm 软链不会动真源数据；若不是软链就停下人工处理）
rm ~/.claude/skills/growatt-nav ~/.codex/skills/growatt-nav
rm ~/.claude/skills/oa-report   ~/.codex/skills/oa-report

# 4) 用「预检并补齐共享 skill 的链接」一节的脚本补建 feishu-nav / sql 链接
#    （先只读预览，确认计划后再 --apply）

# 5) 复跑审计，并重开会话确认各工具能加载新名字
python3 ~/.agents/skills/feishu-nav/scripts/skill-ssot-audit.py
```

以后仓库内再次重命名或删除 skill，同样在每台机器执行：拉取 → 审计定位失效链接 → 人工删除旧软链 → 预检脚本补建 → 复审。

## 审计规则与参数

```bash
python3 ~/.agents/skills/feishu-nav/scripts/skill-ssot-audit.py
# 隔离环境检查；PATH 是模拟 home，不会改变实际 HOME
python3 feishu-nav/scripts/skill-ssot-audit.py --home /path/to/test-home
# 可选：要求 pi 目录及共享链接也齐全
python3 feishu-nav/scripts/skill-ssot-audit.py --require-tool pi
# 可选：明确声明只属于 Codex 的 my-local-skill；可重复此参数
python3 feishu-nav/scripts/skill-ssot-audit.py --tool-specific codex:my-local-skill
```

| 检查 | 达标标准 |
|---|---|
| 共享真源 | `~/.agents/skills` 是真实目录，至少有一个非隐藏 skill 子目录；每个这样的目录须真实且含 `SKILL.md`，目录路径不得通过软链别名 |
| 必需工具 | 默认 Claude、Codex 必须具备对应共享链接；`--require-tool` 可重复追加 `pi`、`cc-switch`、`claude`、`codex` |
| 可选工具 | pi 直接扫描真源，cc-switch 已退役；缺少根目录或共享链接允许，但存在的条目仍检查 |
| 精确链接 | 每个共享条目必须链接到真源中**同名**的 skill 目录；断链、错名/错目标、真实副本均失败 |
| 分发清单 | `.skill-tools` 只能声明真源中的 skill，工具限 claude/codex/pi 且至少含一个链接工具；声明的工具须有链接，未声明的受管工具不得有入口 |
| pi 可见性 | 分发含 pi 的 skill 必须对真源扫描可见；不含 pi 的必须被 `.gitignore`/`.ignore`/`.fdignore` 链路忽略（pi 按此顺序叠加规则，后者可覆盖前者；Git 只读 `.gitignore`） |
| 工具专属 | 仅接受显式 `--tool-specific TOOL:SKILL` 声明的实际 skill 目录，且含 `SKILL.md`；名称必须是非隐藏的单个目录名，不能与真源或其他工具中的条目重名 |
| 检查边界 | 顶层点开头项（如 `.git`、Codex 管理的 `.system`）作为元数据排除检查；其他非隐藏 Codex skill 不自动豁免 |

**只读检测，不修复、不迁移。** 即使重复目录内容相同，也违反共享 skill 的单一真源要求；差异提示只能辅助人工核对。正常检查退出码 0 表示达标、1 表示发现问题；参数错误等其他非零退出也应停止。审计不会执行 skill、调用 CLI、验证认证或确认运行时加载。

## 数据与安全

- 面向企业内部分发（公开仓库）：内网地址与飞书资源坐标受网络边界和账号权限保护，token/id 是定位信息而非访问凭据；连接凭据只存本机受限配置（如 SQL Server `.env` 和 Supabase 用户会话），绝不入库（本仓库历史已重写，确保从未包含凭据）
- `.gitignore` 保留入库 skill 白名单，并排除常见凭据、缓存及导航导出；它无法检查文件内容，也不影响已经被 Git 跟踪的文件，提交前仍需审阅完整 diff
- 不提交 `.env`、应用密钥、访问令牌、登录状态或导出的业务记录；发现已提交秘密时先撤销/轮换，再处理历史，不能只补一条忽略规则
- 业务导出（ndjson 等）统一写入 `~/.agents/skills/.exports/`：隐藏目录不参与 SSOT 审计，且被 Git 忽略；不要写进 `feishu-nav/`、`sql/` 白名单目录，`.gitignore` 的 `*.ndjson` 规则只是兕底
- 不启用 cc-switch 的 skill 复制同步；若它重新生成真实副本，审计只报告问题，需人工处理
- **入库信息分级（脱敏规则）**：凭据、业务事实不入库；坐标类信息可入库。业务信息的权威源（SSOT）是飞书文档/原表，仓库内 skill 只保留坐标入口，不缓存业务数字

  | 类别 | 示例 | 入库 | 兜底机制 |
  |---|---|---|---|
  | 资源坐标 | 飞书 base/wiki token、表/视图 id、URL | ✅ | 飞书侧权限控制，外部无权不可访问 |
  | 基础设施坐标 | 内网 IP、端口、库名、表结构 | ✅ | 内网不可路由 + 只读账号 |
  | 凭据 | 密码、secret、token、`.env` | ❌ | `.gitignore` 硬拦截，只存本地 |
  | 业务事实 | 项目状态/逾期/停更统计、人名、汇报口径、绩效数据 | ❌ | 权威数据在飞书原表，使用时现查 |

- 发现业务事实或凭据误入库时：先从当前树删除，再评估是否需要重写历史；已泄露的凭据先撤销/轮换，不能只补一条忽略规则
