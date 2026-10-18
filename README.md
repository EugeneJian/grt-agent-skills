# Personal Agent Skills · 同步与 SSOT 部署指南

个人 skill 的手动、多机同步方案。共享 skill 的唯一真源（SSOT）是 `~/.agents/skills/`；Git 同步个人内容，安装器独立管理第三方 skill。

## 架构

```text
~/.agents/skills/                         ← 共享 skill 的真实目录
├── feishu-nav/                           ← 本私有 Git 仓库纳管
│   ├── SKILL.md
│   ├── scripts/skill-ssot-audit.py        ← 只读拓扑审计
│   └── tests/
├── sql/                                 ← 本私有 Git 仓库纳管
│   ├── SKILL.md
│   ├── references/schema.md
│   ├── scripts/query.py                   ← 内网 SQL Server 只读查询
│   └── tests/
└── feishu-lark/ 等                       ← 各自安装器管理，不入库

~/.claude/skills/<共享 skill 名>           → 对应真源目录（必需）
~/.codex/skills/<共享 skill 名>            → 对应真源目录（必需）
~/.codex/skills/.system/                  ← Codex 管理的内置例外
~/.pi/agent/skills/                       ← 可不建；pi 直接扫描真源
~/.cc-switch/skills/                      ← 已退役、可不建
```

- 共享 skill 必须是规范目录的非隐藏直接子目录，含 `SKILL.md`，不能再是软链
- Claude/Codex 的同名条目必须是指向该 skill 真身的软链，不能复制一份
- pi、cc-switch 的目录或链接缺失允许；若存在条目，同样检查其归属和链接目标
- Codex 的 `.system` 由工具管理。其他非隐藏的工具专属 skill 需逐项声明，见下文
- 审计仅覆盖顶层非隐藏 skill 条目；`.git`、`.system` 等点开头的元数据项排除检查，不验证其内容，也不支持把个人 skill 藏在这些目录中

两条维护通道独立执行，不自动拉取、推送或迁移：

| 通道 | 内容 | 方式 |
|---|---|---|
| Git | `feishu-nav`、`sql`、README、忽略规则 | 私有仓库 `EugeneJian/personal-agent-skills` |
| 安装器 | `feishu-lark` 等第三方 skill | 按各自官方安装/更新说明维护，不提交到个人仓库 |

## 新电脑部署

以下命令面向 macOS/Linux 终端。已有环境请先盘点；不要直接复制整段执行，也不要删除或覆盖已有目录。

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

GitHub 未登录时，由本人执行 `gh auth login`，选择有此私有仓库访问权限的账号。不要将登录凭据放入仓库。

### 2. 安放个人 skill

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
git clone https://github.com/EugeneJian/personal-agent-skills.git "$HOME/.agents/skills"
```

**如果目录已经非空：停止新机克隆流程。** 若它已是本仓库，检查 `git -C ~/.agents/skills remote -v` 和 `git -C ~/.agents/skills status` 后转到日常维护；若不是，先逐项核对来源、内容差异并另行备份，由本人决定如何合并。不要自动 `rm`、`mv`、重新初始化 Git 或强制覆盖。此指南和审计脚本都不执行迁移。

### 3. 安装 CLI，并由本人完成配置和登录

安装 skill 文件不会自动证明 `lark-cli` 命令可用。依据 [lark-cli 官方安装说明](https://github.com/larksuite/cli/blob/main/README.zh.md)（核对于 2026-10-17），人类用户的安装与配置步骤是：

```bash
npx @larksuite/cli@latest install
command -v lark-cli
lark-cli config init
lark-cli auth login --recommend
lark-cli auth status
```

每步成功后再继续；本人完成交互式配置，并确认所授权的权限。命令找不到时先按安装器提示检查 PATH，认证失败时先处理认证，不要把拓扑审计通过当作修复。

第三方 skill 仍由各自安装器维护。若需要单独安装 larksuite 的 skill，可按官方说明执行 `npx skills add larksuite/cli -g -y`。安装后检查实际落盘位置，不能假设安装器总会生成本仓库要求的布局；发现工具目录中的真实副本时，先停下、比较并备份，再人工决定处理方式。

### 4. 预检并补齐共享 skill 的链接

下面的脚本**默认只读**：检查完全部目标才打印计划，不会删除、移动或替换任何东西。已有真实 skill 目录、普通文件、错误/断裂链接会让它停止；工具根目录及其父目录是软链时也停止。先人工处理这些冲突，再重新预检。

确认计划后，将首行改成 `python3 - --apply <<'PY'` 再执行同一段，才会创建缺失的 Claude/Codex 目录与链接。已正确的链接保持原样。不要用 `ln -sfn` 覆盖已有目录，它可能把新链接建到目录内部。

```bash
python3 - <<'PY'
import sys
from pathlib import Path

home = Path.home().resolve()
source = home / ".agents" / "skills"
roots = [home / ".claude" / "skills", home / ".codex" / "skills"]

def stop(message):
    raise SystemExit("停止：" + message + "；未进入创建阶段")

if sys.argv[1:] not in ([], ["--apply"]):
    stop("只支持无参数预览或 --apply")
if source.parent.is_symlink() or source.is_symlink() or not source.is_dir():
    stop(f"真源必须是无软链别名的实际目录：{source}")
skills = sorted(p for p in source.iterdir()
                if not p.name.startswith(".") and (p.is_dir() or p.is_symlink()))
if any(p.is_symlink() for p in skills):
    stop("真源含软链，请先核对")
if any(not (p / "SKILL.md").is_file() for p in skills):
    stop("真源中的 skill 目录缺少 SKILL.md")
if not skills:
    stop("真源中没有直接包含 SKILL.md 的 skill 目录")

plan = []
for root in roots:
    for p in (root.parent, root):
        if p.is_symlink() or (p.exists() and not p.is_dir()):
            stop(f"工具目录路径异常：{p}")
    for skill in skills:
        target = root / skill.name
        if target.is_symlink():
            if not target.is_dir() or target.resolve() != skill.resolve():
                stop(f"链接目标不匹配：{target}")
        elif target.exists():
            stop(f"已有真实目录或文件：{target}")
        else:
            plan.append((target, skill))

for target, skill in plan:
    print(f"待建：{target} -> {skill}")
if sys.argv[1:] != ["--apply"]:
    print(f"只读预检通过，待建 {len(plan)} 个链接；确认后才用 --apply")
    raise SystemExit(0)
for root in roots:
    root.mkdir(parents=True, exist_ok=True)
for target, skill in plan:
    target.symlink_to(skill, target_is_directory=True)
print(f"已创建 {len(plan)} 个链接；请继续运行审计")
PY
```

该步骤只补齐共享链接，不整理其他现有条目。运行期间不要同时运行其他安装器；若创建中途因权限等错误停止，已创建的链接保留，排除原因后可再次预检并补齐。

### 5. 分别验证布局、认证和工具加载

```bash
python3 ~/.agents/skills/feishu-nav/scripts/skill-ssot-audit.py
lark-cli auth status
```

审计通过只代表目录布局符合下述规则，**不代表 CLI 安装、飞书权限、业务命令或各工具实际加载已验证**。重新打开相关工具的会话，通过各自的 skill 列表/调用入口确认能加载 `feishu-nav`，再对有权访问的导航表做一次只读查询。

## 日常维护

1. 每台机器在开始编辑前，先检查工作区，再拉取。若有未提交工作，先审阅并妥善保存，不能继续照抄后续命令：

   ```bash
   cd "$HOME/.agents/skills"
   git status --short
   # 仅在工作区干净时继续；失败就停止
   git pull --ff-only
   ```

2. `pull --ff-only` 因分叉、冲突或其他原因失败时停止编辑/推送，先检查 `git status` 和提交历史，备份本地工作并人工决定如何整合。不要自动 rebase、强制 push、`reset --hard` 或 `git clean`。
3. 编辑个人内容后，逐步检查并提交；任一步失败都先处理，不要继续：

   ```bash
   python3 -m unittest discover -s feishu-nav/tests -v
   python3 -m unittest discover -s sql/tests -v
   git diff --check
   git diff -- README.md .gitignore feishu-nav/ sql/
   # 人工确认无凭据、导出业务数据或无关变更后再暂存
   git add README.md .gitignore feishu-nav/ sql/
   git diff --cached --check
   git diff --cached
   # 再次确认暂存内容后
   git commit -m "更新个人 skill"
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
| 工具专属 | 仅接受显式 `--tool-specific TOOL:SKILL` 声明的实际 skill 目录，且含 `SKILL.md`；名称必须是非隐藏的单个目录名，不能与真源或其他工具中的条目重名 |
| 检查边界 | 顶层点开头项（如 `.git`、Codex 管理的 `.system`）作为元数据排除检查；其他非隐藏 Codex skill 不自动豁免 |

**只读检测，不修复、不迁移。** 即使重复目录内容相同，也违反共享 skill 的单一真源要求；差异提示只能辅助人工核对。正常检查退出码 0 表示达标、1 表示发现问题；参数错误等其他非零退出也应停止。审计不会执行 skill、调用 CLI、验证认证或确认运行时加载。

## 数据与安全

- 面向企业内部分发（公开仓库）：内网地址与飞书资源坐标受网络边界和账号权限保护，token/id 是定位信息而非访问凭据；连接凭据只存本地 `.env`，绝不入库（本仓库历史已重写，确保从未包含凭据）
- `.gitignore` 保留个人 skill 白名单，并排除常见凭据、缓存及导航导出；它无法检查文件内容，也不影响已经被 Git 跟踪的文件，提交前仍需审阅完整 diff
- 不提交 `.env`、应用密钥、访问令牌、登录状态或导出的业务记录；发现已提交秘密时先撤销/轮换，再处理历史，不能只补一条忽略规则
- 业务导出（ndjson 等）统一写入 `~/.agents/skills/.exports/`：隐藏目录不参与 SSOT 审计，且被 Git 忽略；不要写进 `feishu-nav/`、`sql/` 白名单目录，`.gitignore` 的 `*.ndjson` 规则只是兕底
- 不启用 cc-switch 的 skill 复制同步；若它重新生成真实副本，审计只报告问题，需人工处理
- `SKILL.md` 的业务数字是注明日期的历史快照，正式汇报前须重读原始表格，复核状态、日期和口径
