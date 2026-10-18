#!/usr/bin/env python3
"""Precheck (default) or create (--apply) shared-skill links for Claude/Codex.

Read-only by default: the plan is printed only after every check passes;
nothing is deleted, moved, or replaced. Existing real directories or files,
wrong/dangling links, or symlinked tool roots stop the run before creation.

Windows: creating symbolic links requires Developer Mode or an elevated
PowerShell. Directory junctions are NOT accepted (the SSOT audit treats
them as real copies); run this script instead of mklink /J.
"""

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
