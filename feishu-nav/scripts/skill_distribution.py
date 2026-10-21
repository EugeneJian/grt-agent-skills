#!/usr/bin/env python3
"""SSOT skill 工具分发清单（setup-tool-links 与 skill-ssot-audit 共用）。

分发清单是真源根目录下的 `.skill-tools` 文件，每行一条：

    # 注释
    <skill 名>: <工具>[,工具…]

- 工具名固定为 `claude`、`codex`、`pi`；`pi` 表示「pi 直接扫描真源可见」
- 未列出的 skill 走默认：分发到 claude、codex，且对 pi 可见
- 对 pi 隐藏的 skill 必须同时在真源 `.gitignore`/`.ignore`/`.fdignore`
  链路中被忽略（pi 按 .gitignore → .ignore → .fdignore 顺序叠加规则，
  后者可覆盖前者；Git 只读 .gitignore，不影响入库）
- 审计会校验清单与真源、忽略规则的双向一致性；本模块只负责解析
"""

from pathlib import Path

MANIFEST_NAME = ".skill-tools"
KNOWN_TOOLS = ("claude", "codex", "pi")
DEFAULT_TOOLS = frozenset(KNOWN_TOOLS)
IGNORE_FILES = (".gitignore", ".ignore", ".fdignore")  # 与 pi 的加载顺序一致


def load_distribution(source_root):
    """解析 `<source_root>/.skill-tools`。

    返回 (distribution, problems)：distribution 为 skill 名 -> 工具集合；
    文件不存在时返回空字典。problems 是错误行描述列表（文件级错误也计入），
    有 problems 时 distribution 不完整，调用方应先处理。
    """
    distribution = {}
    problems = []
    manifest = Path(source_root) / MANIFEST_NAME
    if not manifest.exists():
        return distribution, problems
    if manifest.is_symlink() or not manifest.is_file():
        problems.append(f"{manifest} 必须是真实文件")
        return distribution, problems
    try:
        lines = manifest.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        problems.append(f"{manifest} 无法读取: {error}")
        return distribution, problems
    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition(":")
        name = name.strip()
        tools = {tool.strip() for tool in value.split(",") if tool.strip()}
        if not separator or not name or name.startswith(".") or "/" in name or "\\" in name:
            problems.append(f"{manifest}:{lineno} 应为 `<skill 名>: <工具>[,工具…]`：{line}")
            continue
        if not tools or tools - set(KNOWN_TOOLS):
            problems.append(f"{manifest}:{lineno} 工具只能是 {','.join(KNOWN_TOOLS)}：{line}")
            continue
        if name in distribution:
            problems.append(f"{manifest}:{lineno} {name} 重复声明")
            continue
        distribution[name] = frozenset(tools)
    return distribution, problems


def tools_for(distribution, skill):
    """skill 的分发工具集合；未声明时为默认全集。"""
    return distribution.get(skill, DEFAULT_TOOLS)


def _pattern_matches_dir(pattern, name):
    """判断规则是否作用于真源顶层的 skill 目录 `name`。

    只覆盖这些文件实际使用的模式：`*`、`name`、`name/`、`name/**`。
    `name/**` 只匹配目录内部，不影响目录自身；带路径前缀或其他通配
    （如 `*.log`）不会等于顶层 skill 名，按不匹配处理。
    """
    if pattern.endswith("/**"):
        return False
    base = pattern.rstrip("/")
    if "/" in base:
        return False
    if base == "*":
        return True
    return base == name


def pi_ignores(source_root, skill):
    """按 pi 的规则叠加忽略文件，判断真源中的 skill 目录对 pi 是否隐藏。

    返回 (ignored, rule_file)：规则按 IGNORE_FILES 顺序叠加，最后命中的
    规则生效（与 pi 加载器、Git 的 last-match-wins 一致）。没有任何规则
    命中时目录可见。
    """
    ignored = False
    rule_file = None
    for filename in IGNORE_FILES:
        path = Path(source_root) / filename
        if path.is_symlink() or not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for raw in lines:
            rule = raw.strip()
            if not rule or rule.startswith("#"):
                continue
            negate = rule.startswith("!")
            pattern = rule[1:] if negate else rule
            if _pattern_matches_dir(pattern, skill):
                ignored = not negate
                rule_file = filename
    return ignored, rule_file
