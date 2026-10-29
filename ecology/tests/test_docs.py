"""Offline checks for Ecology Skill discovery metadata and documentation syntax."""

import json
from pathlib import Path
import re
import unittest
from urllib.parse import unquote, urlsplit

import yaml


SKILL = Path(__file__).resolve().parents[1]
ROOT = SKILL.parent
DOCS = sorted(SKILL.rglob("*.md"))


def anchors(text):
    """Resolve the conventional Markdown heading anchors used by these documents."""
    return {
        re.sub(r"[^\w\s-]", "", heading.strip().lower()).replace(" ", "-")
        for heading in re.findall(r"^#{1,6}\s+(.+)$", text, re.MULTILINE)
    }


def invalid_constant(value):
    raise ValueError(f"Not a JSON constant: {value}")


class EcologyDocsTests(unittest.TestCase):
    def test_skill_frontmatter_supports_discovery(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---(?:\n|$)", text, re.DOTALL)
        self.assertIsNotNone(match, "SKILL.md needs YAML frontmatter")
        fields = yaml.safe_load(match.group(1))
        self.assertIsInstance(fields, dict)
        self.assertEqual(fields.get("name"), SKILL.name)
        description = fields.get("description")
        self.assertIsInstance(description, str)
        self.assertTrue(description.strip())
        self.assertLessEqual(len(description), 1024)

    def test_agent_metadata_is_valid_yaml(self):
        fields = yaml.safe_load((SKILL / "agents/openai.yaml").read_text(encoding="utf-8"))
        self.assertIsInstance(fields, dict)
        self.assertIsInstance(fields.get("interface"), dict)
        self.assertTrue(fields["interface"].get("display_name"))

    def test_local_markdown_references_resolve(self):
        for doc in DOCS:
            text = doc.read_text(encoding="utf-8")
            for href in re.findall(r"\[[^]\n]+\]\(([^)]+)\)", text):
                link = urlsplit(href)
                if link.scheme or link.netloc:
                    continue
                with self.subTest(document=doc.relative_to(ROOT), link=href):
                    target = (doc.parent / unquote(link.path)).resolve() if link.path else doc
                    self.assertTrue(target.is_relative_to(ROOT), "Local links must stay in the checkout")
                    self.assertTrue(target.is_file(), "Missing local reference")
                    if link.fragment and target.suffix == ".md":
                        self.assertIn(unquote(link.fragment), anchors(target.read_text(encoding="utf-8")))

    def test_json_examples_are_parseable(self):
        count = 0
        for doc in DOCS:
            text = doc.read_text(encoding="utf-8")
            examples = re.findall(r"^```json[ \t]*\n(.*?)^```[ \t]*$", text, re.MULTILINE | re.DOTALL)
            # Inline tool calls are executable examples; field-shape pseudocode is not JSON.
            for code in re.findall(r"`([^`\n]+)`", text):
                call = re.fullmatch(r"[a-zA-Z_]\w*\((\{.*\})\)", code)
                if call:
                    examples.append(call.group(1))
            for example in examples:
                with self.subTest(document=doc.relative_to(ROOT), example=count):
                    json.loads(example, parse_constant=invalid_constant)
                count += 1
        self.assertGreater(count, 0, "Keep at least one executable JSON example")


if __name__ == "__main__":
    unittest.main()
