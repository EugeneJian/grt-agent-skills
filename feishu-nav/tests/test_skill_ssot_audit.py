"""Regression tests: all skill fixtures live in an isolated temporary home."""

import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/skill-ssot-audit.py"
SPEC = importlib.util.spec_from_file_location("skill_ssot_audit", SCRIPT)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="skill-ssot-test-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.canonical = self.home / ".agents/skills"
        self.roots = {tool: self.home / path for tool, path in AUDIT.TOOL_PATHS.items()}

    def skill(self, root, name="example", text="shared skill\n"):
        path = root / name
        path.mkdir(parents=True)
        (path / "SKILL.md").write_text(text)
        return path

    def valid(self, name="example"):
        source = self.skill(self.canonical, name)
        for tool in AUDIT.DEFAULT_REQUIRED:
            self.roots[tool].mkdir(parents=True, exist_ok=True)
            (self.roots[tool] / name).symlink_to(source, target_is_directory=True)
        return source

    def run_audit(self, **kwargs):
        output = []
        result = AUDIT.audit(self.home, emit=output.append, **kwargs)
        return result, "\n".join(output)

    def manifest(self, text):
        (self.canonical / ".skill-tools").write_text(text, encoding="utf-8")

    def ignore_rule(self, text, filename=".ignore"):
        (self.canonical / filename).write_text(text, encoding="utf-8")

    def fails(self, marker, **kwargs):
        result, output = self.run_audit(**kwargs)
        self.assertEqual(result, 1, output)
        self.assertIn(marker, output)
        self.assertNotIn("✓ SSOT 达标", output)

    def test_valid_topology_optional_roots_absent(self):
        self.valid()
        result, output = self.run_audit()
        self.assertEqual(result, 0, output)
        self.assertIn("✓ SSOT 达标", output)

    def test_all_roots_absent_fails(self):
        self.fails("缺失目录")

    def test_empty_canonical_fails(self):
        self.canonical.mkdir(parents=True)
        for tool in AUDIT.DEFAULT_REQUIRED:
            self.roots[tool].mkdir(parents=True)
        self.fails("空真源")

    def test_unique_source_in_wrong_root_fails(self):
        self.canonical.mkdir(parents=True)
        source = self.skill(self.roots["pi"])
        for tool in AUDIT.DEFAULT_REQUIRED:
            self.roots[tool].mkdir(parents=True)
            (self.roots[tool] / "example").symlink_to(source)
        self.fails("真源缺失")

    def test_missing_canonical_root_with_valid_tool_targets_fails(self):
        source = self.skill(self.home / "elsewhere")
        for tool in AUDIT.DEFAULT_REQUIRED:
            self.roots[tool].mkdir(parents=True)
            (self.roots[tool] / "example").symlink_to(source)
        self.fails("缺失目录")

    def test_wrong_existing_target_fails(self):
        self.valid()
        other = self.skill(self.home / "elsewhere")
        link = self.roots["claude"] / "example"
        link.unlink()
        link.symlink_to(other)
        self.fails("错误目标")

    def test_link_to_different_canonical_skill_fails(self):
        self.valid()
        other = self.valid("second")
        link = self.roots["codex"] / "example"
        link.unlink()
        link.symlink_to(other)
        self.fails("错误目标")

    def test_missing_skill_markdown_fails(self):
        source = self.valid()
        (source / "SKILL.md").unlink()
        self.fails("缺失 SKILL.md")

    def test_canonical_symlink_fails(self):
        source = self.valid()
        other = self.home / "relocated"
        source.rename(other)
        source.symlink_to(other)
        self.fails("非规范真身")

    def test_canonical_root_symlink_fails(self):
        self.valid()
        other = self.home / "relocated-root"
        self.canonical.rename(other)
        self.canonical.symlink_to(other)
        self.fails("目录类型")

    def test_canonical_ancestor_symlink_fails(self):
        self.valid()
        ancestor = self.home / ".agents"
        other = self.home / "relocated-agents"
        ancestor.rename(other)
        ancestor.symlink_to(other)
        self.fails("目录类型")

    def test_tool_ancestor_symlink_fails(self):
        self.valid()
        ancestor = self.home / ".claude"
        other = self.home / "relocated-claude"
        ancestor.rename(other)
        ancestor.symlink_to(other)
        self.fails("目录类型")

    def test_missing_required_root_fails(self):
        self.valid()
        shutil.rmtree(self.roots["claude"])
        self.fails("缺失目录")

    def test_missing_required_link_fails(self):
        self.valid()
        (self.roots["codex"] / "example").unlink()
        self.fails("缺失入口")

    def test_relative_links_are_valid(self):
        source = self.valid()
        link = self.roots["claude"] / "example"
        link.unlink()
        link.symlink_to(os.path.relpath(source, link.parent))
        result, output = self.run_audit()
        self.assertEqual(result, 0, output)

    def test_dangling_optional_link_fails(self):
        self.valid()
        self.roots["pi"].mkdir(parents=True)
        (self.roots["pi"] / "example").symlink_to(self.home / "absent")
        self.fails("断链/循环")

    def test_link_loop_fails(self):
        self.valid()
        link = self.roots["claude"] / "example"
        link.unlink()
        link.symlink_to("example")
        self.fails("断链/循环")

    def test_identical_duplicate_fails(self):
        source = self.valid()
        self.roots["pi"].mkdir(parents=True)
        shutil.copytree(source, self.roots["pi"] / "example")
        self.fails("内容暂一致")

    def test_diverged_duplicate_fails(self):
        self.valid()
        self.skill(self.roots["pi"], text="different content\n")
        self.fails("内容已分叉")

    def test_valid_optional_links(self):
        source = self.valid()
        for tool in ("pi", "cc-switch"):
            self.roots[tool].mkdir(parents=True)
            (self.roots[tool] / "example").symlink_to(source)
        result, output = self.run_audit()
        self.assertEqual(result, 0, output)

    def test_optional_file_collision_fails(self):
        self.valid()
        for tool in ("pi", "cc-switch"):
            with self.subTest(tool=tool):
                self.roots[tool].mkdir(parents=True)
                collision = self.roots[tool] / "example"
                collision.write_text("not a skill link")
                self.fails("非软链副本")
                collision.unlink()

    def test_additional_required_tool_root_fails_when_absent(self):
        self.valid()
        self.fails("缺失目录", required_tools=["pi"])

    def test_additional_required_tool_link_fails_when_absent(self):
        self.valid()
        self.roots["cc-switch"].mkdir(parents=True)
        self.fails("缺失入口", required_tools=["cc-switch"])

    def test_unlisted_tool_specific_skill_fails(self):
        self.valid()
        self.skill(self.roots["codex"], "helper")
        self.fails("真源缺失")

    def test_explicit_tool_specific_skill_passes(self):
        self.valid()
        self.skill(self.roots["codex"], "helper")
        result, output = self.run_audit(tool_specific={"helper": "codex"})
        self.assertEqual(result, 0, output)

    def test_missing_tool_specific_skill_fails(self):
        self.valid()
        self.fails("例外无效", tool_specific={"helper": "codex"})

    def test_tool_specific_must_have_skill_markdown(self):
        self.valid()
        (self.roots["codex"] / "helper").mkdir()
        self.fails("例外无效", tool_specific={"helper": "codex"})

    def test_tool_specific_cannot_hide_shared_skill(self):
        self.valid()
        self.fails("例外冲突", tool_specific={"example": "codex"})

    def test_tool_specific_cannot_appear_in_other_tool(self):
        self.valid()
        helper = self.skill(self.roots["codex"], "helper")
        self.roots["pi"].mkdir(parents=True)
        (self.roots["pi"] / "helper").symlink_to(helper)
        self.fails("例外冲突", tool_specific={"helper": "codex"})

    def test_codex_system_is_tool_managed(self):
        self.valid()
        self.skill(self.roots["codex"] / ".system", "tool-helper")
        result, output = self.run_audit()
        self.assertEqual(result, 0, output)

    def test_hidden_metadata_is_outside_shared_scope(self):
        self.valid()
        for root in (self.canonical, self.roots["codex"]):
            self.skill(root, ".hidden-metadata")
        result, output = self.run_audit()
        self.assertEqual(result, 0, output)

    def test_installed_skills_need_no_git_tracking(self):
        self.valid("feishu-nav")
        self.valid("lark-shared")
        result, output = self.run_audit()
        self.assertEqual(result, 0, output)

    def test_tool_root_symlink_is_rejected(self):
        self.valid()
        shutil.rmtree(self.roots["claude"])
        self.roots["claude"].symlink_to(self.canonical)
        self.fails("目录类型")

    def test_restricted_distribution_passes_without_codex_link(self):
        source = self.skill(self.canonical, "claude-only-skill")
        self.manifest("claude-only-skill: claude\n")
        self.ignore_rule("claude-only-skill/\n")
        for tool in AUDIT.DEFAULT_REQUIRED:
            self.roots[tool].mkdir(parents=True, exist_ok=True)
        (self.roots["claude"] / "claude-only-skill").symlink_to(source)
        result, output = self.run_audit()
        self.assertEqual(result, 0, output)
        self.assertIn("claude-only-skill @ pi 已隐藏", output)

    def test_restricted_distribution_rejects_undeclared_tool_link(self):
        source = self.skill(self.canonical, "claude-only-skill")
        self.manifest("claude-only-skill: claude\n")
        self.ignore_rule("claude-only-skill/\n")
        for tool in AUDIT.DEFAULT_REQUIRED:
            self.roots[tool].mkdir(parents=True, exist_ok=True)
            (self.roots[tool] / "claude-only-skill").symlink_to(source)
        self.fails("未分发却存在")

    def test_restricted_distribution_requires_declared_tool_link(self):
        self.skill(self.canonical, "claude-only-skill")
        self.manifest("claude-only-skill: claude\n")
        self.ignore_rule("claude-only-skill/\n")
        for tool in AUDIT.DEFAULT_REQUIRED:
            self.roots[tool].mkdir(parents=True, exist_ok=True)
        self.fails("缺失入口")

    def test_pi_hidden_skill_requires_ignore_rule(self):
        source = self.skill(self.canonical, "claude-only-skill")
        self.manifest("claude-only-skill: claude\n")
        for tool in AUDIT.DEFAULT_REQUIRED:
            self.roots[tool].mkdir(parents=True, exist_ok=True)
        (self.roots["claude"] / "claude-only-skill").symlink_to(source)
        self.fails("pi 应隐藏")

    def test_default_distribution_rejects_accidental_pi_hide(self):
        self.valid()
        self.ignore_rule("example/\n")
        self.fails("pi 不可见")

    def test_ignore_layering_later_file_rehides_whitelisted_skill(self):
        self.valid()
        self.ignore_rule("*\n!example/\n!example/**\n", filename=".gitignore")
        result, output = self.run_audit()
        self.assertEqual(result, 0, output)  # .gitignore 白名单保持可见
        self.ignore_rule("example/\n")      # .ignore 后叠加，重新隐藏
        self.fails("pi 不可见")

    def test_manifest_stale_entry_fails(self):
        self.valid()
        self.manifest("ghost-skill: claude\n")
        self.fails("不在真源中")

    def test_manifest_malformed_lines_fail(self):
        self.valid()
        for text in ("no-colon-line\n", "example: terminal\n", "example: \n",
                     "example: claude\nexample: codex\n"):
            with self.subTest(text=text.strip()):
                self.manifest(text)
                self.fails("清单无效")
                (self.canonical / ".skill-tools").unlink()

    def test_manifest_symlink_fails(self):
        self.valid()
        other = self.home / "manifest-elsewhere"
        other.write_text("example: claude\n")
        (self.canonical / ".skill-tools").symlink_to(other)
        self.fails("清单无效")

    def test_cli_exit_codes_use_only_temporary_home(self):
        # Apple Python (macOS CommandLineTools) writes its bytecode cache into
        # $HOME/Library/Caches on startup. That is interpreter behaviour, not
        # the audit script touching $HOME, so redirect the cache to keep this
        # assertion meaningful on macOS as well.
        environment = dict(os.environ, HOME=str(self.home / "unused-home"),
                           PYTHONPYCACHEPREFIX=str(self.home / "pycache"))
        command = [sys.executable, str(SCRIPT), "--home", str(self.home)]
        missing = subprocess.run(command, env=environment, capture_output=True, text=True)
        self.assertEqual(missing.returncode, 1, missing.stdout + missing.stderr)
        self.valid()
        good = subprocess.run(command, env=environment, capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
        self.assertFalse((self.home / "unused-home").exists())

    def test_cli_rejects_unsafe_exception_paths(self):
        for value in ("codex:../outside", "unknown:helper", "codex:.system", "codex:helper:other"):
            with self.subTest(value=value):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT), "--home", str(self.home), "--tool-specific", value],
                    capture_output=True, text=True,
                    env=dict(os.environ, HOME=str(self.home / "unused-home")),
                )
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
