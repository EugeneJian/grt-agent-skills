#!/usr/bin/env python3
"""Read-only audit of skill sources, links, and required tool visibility.

Shared skills live in real directories at ~/.agents/skills/<name>/SKILL.md.
Claude and Codex require matching links. Pi scans the canonical root natively;
its links and the retired cc-switch root are optional, but checked if present.
Skills declared in the root .skill-tools manifest are distributed to a subset
of tools only (e.g. claude-code-toolsearch is Claude Code exclusive): the
manifest tools must have their links, other tools must NOT have entries, and
pi scan visibility of the canonical root must match (hidden skills require
.gitignore/.ignore/.fdignore rules that pi layers in that order).
Hidden top-level metadata (including Codex .system) is outside the shared set.
Other tool-only skills require explicit --tool-specific TOOL:SKILL exceptions.
No Git tracking, CLI authentication, runtime loading, or repair is performed.
"""

import argparse
import hashlib
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skill_distribution import (IGNORE_FILES, KNOWN_TOOLS, load_distribution,
                                 pi_ignores, tools_for)


TOOL_PATHS = {
    "pi": Path(".pi/agent/skills"),
    "claude": Path(".claude/skills"),
    "codex": Path(".codex/skills"),
    "cc-switch": Path(".cc-switch/skills"),
}
DEFAULT_REQUIRED = {"claude", "codex"}


def present(path):
    """Unlike exists(), count dangling links as present."""
    return os.path.lexists(path)


def dhash(root):
    """Compare duplicate content without following internal directory links."""
    h = hashlib.sha256()
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs.sort()
        for name in sorted(dirs + files):
            if name == ".DS_Store":
                continue
            path = Path(directory) / name
            h.update(str(path.relative_to(root)).encode())
            h.update(b"\0")
            if path.is_symlink():
                h.update(b"link\0" + os.readlink(path).encode())
            elif path.is_file():
                h.update(b"file\0")
                with path.open("rb") as source:
                    for chunk in iter(lambda: source.read(65536), b""):
                        h.update(chunk)
            else:
                h.update(b"directory\0")
            h.update(b"\0")
    return h.hexdigest()[:12]


def audit(home, required_tools=None, tool_specific=None, distribution=None, emit=print):
    """Audit configured roots for the supplied home; return 0 (pass) or 1 (fail)."""
    home = Path(home).resolve()
    required = DEFAULT_REQUIRED | set(required_tools or ())
    exceptions = dict(tool_specific or {})  # skill name -> owning tool
    roots = {"agents": home / ".agents/skills"}
    roots.update({tool: home / suffix for tool, suffix in TOOL_PATHS.items()})
    problems = []
    entries = {}
    valid_roots = set()

    def fail(message):
        problems.append(message)
        emit("  ❌ " + message)

    emit("== 目录与真源 ==")
    for label, root in roots.items():
        must_exist = label == "agents" or label in required or label in exceptions.values()
        entries[label] = {}
        # Ancestor aliases must not silently relocate a canonical/tool root.
        # Resolve the caller's home once so system aliases (e.g. macOS /var)
        # outside that boundary do not cause false failures.
        aliases = [path for path in [root, *root.parents] if home in path.parents and path.is_symlink()]
        if aliases:
            fail(f"[目录类型] {label} 的目录路径含软链: {aliases[0]}")
            continue
        if not present(root):
            if must_exist:
                fail(f"[缺失目录] {label}: {root}")
            else:
                emit(f"  可选入口未启用: {label}")
            continue
        if root.is_symlink() or not root.is_dir():
            fail(f"[目录类型] {label} 必须是真实目录: {root}")
            continue
        try:
            for path in sorted(root.iterdir()):
                if path.name.startswith("."):
                    # Hidden metadata, including Codex .system, is not a shared skill.
                    continue
                if path.is_symlink() or path.is_dir():
                    entries[label][path.name] = path
            valid_roots.add(label)
        except OSError as error:
            fail(f"[无法读取] {root}: {error}")

    shared = entries["agents"]
    if not shared:
        fail("[空真源] 规范目录没有可审计的 skill")

    for name, path in sorted(shared.items()):
        if path.is_symlink() or not path.is_dir():
            fail(f"[非规范真身] {name}: {path} 必须是真实目录")
            continue
        if not (path / "SKILL.md").is_file():
            fail(f"[缺失 SKILL.md] {name}: {path / 'SKILL.md'}")

    emit("\n== 工具分发清单 ==")
    if distribution is None:
        distribution, manifest_problems = load_distribution(roots["agents"])
        for problem in manifest_problems:
            fail(f"[清单无效] {problem}")
    for name in sorted(set(distribution) - set(shared)):
        fail(f"[清单无效] {name} 不在真源中（.skill-tools 声明了不存在的 skill）")
    for name in sorted(set(distribution) & set(shared)):
        if not (set(distribution[name]) - {"pi"}):
            fail(f"[清单无效] {name} 至少要分发到一个链接工具（claude/codex）")
        else:
            emit(f"  分发: {name} -> {', '.join(sorted(tools_for(distribution, name)))}")

    emit("\n== 工具专用例外 ==")
    for name, owner in sorted(exceptions.items()):
        if owner not in valid_roots:
            continue  # Its required root already failed; do not traverse it.
        path = roots[owner] / name
        if "agents" in valid_roots and present(roots["agents"] / name):
            fail(f"[例外冲突] {name} 同时存在于规范目录，不能声明为 {owner} 专用")
        if path.is_symlink() or not path.is_dir() or not (path / "SKILL.md").is_file():
            fail(f"[例外无效] {owner}:{name} 必须是含 SKILL.md 的真实目录: {path}")
        else:
            emit(f"  专用例外: {owner}:{name}")
        for other in TOOL_PATHS:
            if other != owner and other in valid_roots and present(roots[other] / name):
                fail(f"[例外冲突] {name} 声明为 {owner} 专用，但也出现在 {other}")

    emit("\n== 软链与可见性 ==")
    for tool in TOOL_PATHS:
        if tool not in valid_roots:
            continue
        names = set(entries[tool])
        names.update(name for name in shared if tool in required or present(roots[tool] / name))
        for name in sorted(names):
            if exceptions.get(name) == tool:
                continue
            path = roots[tool] / name
            canonical = roots["agents"] / name
            managed = tool in KNOWN_TOOLS  # 分发清单只约束 claude/codex/pi
            if not present(path):
                if (name in shared and tool in required
                        and (not managed or tool in tools_for(distribution, name))):
                    fail(f"[缺失入口] {name} @ {tool}: {path}")
                continue
            if name in shared and managed and tool not in tools_for(distribution, name):
                fail(f"[未分发却存在] {name} @ {tool}: 分发清单不含 {tool}，请人工删除: {path}")
                continue
            if name not in shared:
                fail(f"[真源缺失] {name} @ {tool}: 应存在 {canonical / 'SKILL.md'}；工具专用项需显式例外")
            if not path.is_symlink():
                fail(f"[非软链副本] {name} @ {tool}: {path}")
                continue
            if "agents" not in valid_roots:
                continue  # Canonical root already failed; never follow an alias through it.
            try:
                resolved = path.resolve(strict=True)
            except (OSError, RuntimeError) as error:
                fail(f"[断链/循环] {name} @ {tool}: {path} ({error})")
                continue
            # Compare to the exact expected path, not canonical.resolve(), which
            # could hide an invalid canonical symlink or a link to another skill.
            expected = canonical.parent.resolve() / name
            if resolved != expected:
                fail(f"[错误目标] {name} @ {tool}: {resolved}，应为 {expected}")
            elif not (resolved / "SKILL.md").is_file():
                fail(f"[缺失 SKILL.md] {name} @ {tool}: {resolved}")
            else:
                emit(f"  ✓ {name} @ {tool} -> {expected}")

    emit("\n== pi 扫描可见性 ==")
    if "agents" in valid_roots:
        for name in sorted(shared):
            expect_visible = "pi" in tools_for(distribution, name)
            ignored, rule_file = pi_ignores(roots["agents"], name)
            if expect_visible and ignored:
                fail(f"[pi 不可见] {name} 被 {rule_file} 忽略，但分发清单要求 pi 可见")
            elif not expect_visible and not ignored:
                fail(f"[pi 应隐藏] {name} 分发清单不含 pi，需在 {'/'.join(IGNORE_FILES)} 中忽略，"
                     f"否则 pi 扫描真源会加载它")
            else:
                emit(f"  ✓ {name} @ pi {'可见' if expect_visible else '已隐藏'}")

    emit("\n== 重复真身 ==")
    real = {}
    for label, found in entries.items():
        for name, path in found.items():
            if not path.is_symlink() and path.is_dir():
                real.setdefault(name, []).append((label, path))
    for name, locations in sorted(real.items()):
        if len(locations) <= 1:
            continue
        try:
            hashes = {label: dhash(path) for label, path in locations}
            state = "内容已分叉" if len(set(hashes.values())) > 1 else "内容暂一致"
            fail(f"[重复真身] {name}: {state} {hashes}")
        except OSError as error:
            fail(f"[重复真身] {name}: 内容比较失败 ({error})")

    emit("\n结论: " + (f"❌ {len(problems)} 个问题需处理" if problems else "✓ SSOT 达标"))
    emit("仅检查目录拓扑；不会修复、同步或验证 CLI 登录及 agent 实际加载。")
    return 1 if problems else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=None, help="检查指定 home（默认当前用户）；测试使用临时目录")
    parser.add_argument("--require-tool", action="append", choices=sorted(TOOL_PATHS), default=[],
                        help="额外要求该工具目录和所有共享 skill 入口；可重复，默认已要求 claude/codex")
    parser.add_argument("--tool-specific", action="append", default=[], metavar="TOOL:SKILL",
                        help="明确声明仅属于单一工具的真实 skill；可重复，例如 codex:my-codex-helper")
    args = parser.parse_args(argv)
    exceptions = {}
    for value in args.tool_specific:
        tool, separator, name = value.partition(":")
        if (not separator or tool not in TOOL_PATHS or not name or name.startswith(".")
                or "/" in name or "\\" in name or ":" in name):
            parser.error("--tool-specific 必须为 TOOL:SKILL，SKILL 是非隐藏的单个目录名")
        if name in exceptions and exceptions[name] != tool:
            parser.error(f"{name} 不能同时声明为多个工具专用")
        exceptions[name] = tool
    try:
        return audit(args.home if args.home is not None else Path.home(), args.require_tool, exceptions)
    except (OSError, RuntimeError) as error:
        print(f"❌ 审计无法完成: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
