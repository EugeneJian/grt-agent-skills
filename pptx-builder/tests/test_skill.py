"""The Skill entry follows the repository conventions: short SKILL.md, valid front matter, working links."""

from pathlib import Path
import re
import unittest

SKILL = Path(__file__).resolve().parents[1]
TEXT = (SKILL / "SKILL.md").read_text(encoding="utf-8")


class SkillEntryTests(unittest.TestCase):
    def test_front_matter_names_the_folder_and_describes_the_skill(self):
        front = TEXT.split("---", 2)[1]
        self.assertRegex(front, rf"(?m)^name: {SKILL.name}$")
        description = re.search(r"(?m)^description: (.+)$", front).group(1)
        self.assertTrue(40 <= len(description) <= 1024)

    def test_the_entry_stays_short(self):
        self.assertLessEqual(len(TEXT.splitlines()), 100)

    def test_every_link_points_at_a_file_in_the_skill(self):
        for document in (SKILL / "SKILL.md", *(SKILL / "references").glob("*.md")):
            for target in re.findall(r"\]\(([^)#]+)\)", document.read_text(encoding="utf-8")):
                if "://" in target or target.startswith("/"):
                    continue
                with self.subTest(document=document.name, target=target):
                    self.assertTrue((document.parent / target).is_file())


if __name__ == "__main__":
    unittest.main()
