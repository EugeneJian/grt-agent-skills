"""Keep completed decks and competing writes separate until publication."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Barrier
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

try:
    from pptx import Presentation
except ImportError:
    raise unittest.SkipTest("python-pptx is not installed") from None

import deck as builder


class OutputTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(TemporaryDirectory()))
        self.target = self.folder / "deck.pptx"
        self.made = builder.Deck({"slides": [{"layout": "closing"}]})
        self.made.build()

    def test_an_existing_deck_cannot_be_overwritten_even_as_its_own_template(self):
        template = Presentation()
        template.save(str(self.target))
        original = self.target.read_bytes()
        source = self.folder / "deck.json"
        source.write_text('{"slides": [{"layout": "closing"}]}', encoding="utf-8")
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as errors:
            code = builder.main([str(source), str(self.target), "--template", str(self.target)])
        self.assertEqual(code, 2)
        self.assertIn("already exists", errors.getvalue())
        self.assertEqual(self.target.read_bytes(), original)
        self.assertCountEqual(self.folder.iterdir(), [source, self.target])

    def test_an_output_created_during_serialization_is_preserved(self):
        save = self.made.prs.save

        def competing_save(path):
            save(path)
            self.target.write_bytes(b"created by another writer")

        with patch.object(self.made.prs, "save", competing_save):
            with self.assertRaisesRegex(builder.SpecError, "already exists"):
                self.made.save(self.target)
        self.assertEqual(self.target.read_bytes(), b"created by another writer")
        self.assertEqual(list(self.folder.iterdir()), [self.target])

    def test_overlapping_writers_stage_separately_and_publish_only_one_deck(self):
        started = Barrier(2)
        drafts = []

        def write(data):
            made = builder.Deck({"slides": [{"layout": "closing"}]})
            made.build()

            def serialize(path):
                drafts.append(Path(path))
                Path(path).write_bytes(data)
                started.wait(timeout=5)

            with patch.object(made.prs, "save", serialize):
                try:
                    made.save(self.target)
                except builder.SpecError:
                    return None
                return data

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(write, (b"deck A", b"deck B")))
        self.assertEqual(len(set(drafts)), 2)
        self.assertEqual(outcomes.count(None), 1)
        self.assertIn(self.target.read_bytes(), outcomes)
        self.assertEqual(list(self.folder.iterdir()), [self.target])

    def test_interrupted_serialization_cleans_up_its_draft(self):
        def broken_save(path):
            Path(path).write_bytes(b"partial deck")
            raise OSError("write interrupted")

        with patch.object(self.made.prs, "save", broken_save):
            with self.assertRaisesRegex(OSError, "write interrupted"):
                self.made.save(self.target)
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_a_filesystem_without_hard_links_reports_the_limitation(self):
        posix = SimpleNamespace(name="posix", link=Mock(side_effect=OSError("links unsupported")))
        with patch.object(builder, "os", posix):
            with self.assertRaisesRegex(builder.SpecError, "hard links"):
                self.made.save(self.target)
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_windows_uses_a_non_replacing_rename_without_hard_links(self):
        def rename(draft, output):
            if output.exists():
                raise FileExistsError()
            draft.rename(output)

        windows = SimpleNamespace(name="nt", rename=Mock(side_effect=rename))
        with patch.object(builder, "os", windows):
            self.made.save(self.target)
            original = self.target.read_bytes()
            with self.assertRaisesRegex(builder.SpecError, "already exists"):
                self.made.save(self.target)
        self.assertEqual(windows.rename.call_count, 2)
        self.assertEqual(self.target.read_bytes(), original)
        self.assertEqual(list(self.folder.iterdir()), [self.target])


if __name__ == "__main__":
    unittest.main()
