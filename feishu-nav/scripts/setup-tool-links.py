#!/usr/bin/env python3
"""Precheck (default) or create (--apply) shared-skill links for Claude/Codex.

Read-only by default: the plan is printed only after every check passes;
nothing is deleted, moved, or replaced. Existing real directories or files,
wrong/dangling links, or symlinked tool roots stop the run before creation.
Skills declared in the root .skill-tools manifest are linked only to their
distributed tools; an entry found at a non-distributed tool stops the run
for manual removal (this script never deletes anything).

Windows: creating symbolic links requires Developer Mode or an elevated
PowerShell. Directory junctions are NOT accepted (the SSOT audit treats
them as real copies); run this script instead of mklink /J.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skill_distribution import load_distribution, tools_for

home = Path.home().resolve()
source = home / ".agents" / "skills"
roots = [("claude", home / ".claude" / "skills"), ("codex", home / ".codex" / "skills")]

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
distribution, manifest_problems = load_distribution(source)
for problem in manifest_problems:
    stop(f"分发清单无效：{problem}")
stale = sorted(set(distribution) - {p.name for p in skills})
if stale:
    stop(f"分发清单声明了不存在的 skill：{', '.join(stale)}")

plan = []
for tool, root in roots:
    for p in (root.parent, root):
        if p.is_symlink() or (p.exists() and not p.is_dir()):
            stop(f"工具目录路径异常：{p}")
    for skill in skills:
        target = root / skill.name
        if tool not in tools_for(distribution, skill.name):
            if target.is_symlink() or target.exists():
                stop(f"分发清单不含 {tool}，但存在入口 {target}；请人工删除后重跑")
            print(f"不分发：{target}")
            continue
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
for _, root in roots:
    root.mkdir(parents=True, exist_ok=True)
for target, skill in plan:
    target.symlink_to(skill, target_is_directory=True)
print(f"已创建 {len(plan)} 个链接；请继续运行审计")
