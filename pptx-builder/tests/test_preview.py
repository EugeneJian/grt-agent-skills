"""Exercise the preview command with synthetic PNGs on any platform."""

from contextlib import redirect_stdout
import io
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

try:
    from PIL import Image
    from pptx import Presentation
except ImportError:
    raise unittest.SkipTest("python-pptx is not installed")

import preview


class PreviewCommandTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(TemporaryDirectory())).resolve()
        self.present = Presentation()
        for _ in range(3):
            self.present.slides.add_slide(self.present.slide_layouts[6])
        self.deck = self.folder / "Report v1.pptx"
        self.present.save(self.deck)

    def run_preview(self, deck=None, output=None, *, missing=()):
        args = [str(deck or self.deck)]
        if output is not None:
            args.extend(("--out", str(output)))

        def render(copy, folder, size):
            number = int(copy.stem.rsplit("-", 1)[1])
            if number in missing:
                return None
            target = folder / f"{copy.name}.png"
            Image.new("RGB", (size, size // 2), "white").save(target)
            return target

        with (patch.object(preview.sys, "platform", "darwin"),
              patch.object(preview.shutil, "which", return_value="qlmanage"),
              patch.object(preview, "render", side_effect=render),
              redirect_stdout(io.StringIO()) as status):
            code = preview.main(args)
        return code, status.getvalue()

    def test_default_preview_keeps_deck_versions_separate(self):
        next_deck = self.folder / "Report v2.pptx"
        self.present.save(next_deck)
        self.assertEqual(self.run_preview()[0], 0)
        self.assertEqual(self.run_preview(next_deck)[0], 0)
        for document in (self.deck, next_deck):
            with self.subTest(deck=document):
                out = self.folder / "preview" / document.stem
                self.assertEqual(sorted(p.name for p in out.iterdir()),
                                 ["overview.png", "slide-01.png", "slide-02.png", "slide-03.png"])

    def test_partial_preview_is_incomplete_and_keeps_source_numbers(self):
        out = self.folder / "chosen output"
        self.assertEqual(self.run_preview(output=out)[0], 0)
        unrelated = out / "slide-diagram.png"
        unrelated.write_bytes(b"unrelated work")
        with patch.object(preview.ImageDraw, "Draw") as drawing:
            code, status = self.run_preview(output=out, missing=(2,))
        self.assertNotEqual(code, 0)
        self.assertIn("could not draw slide(s): 2", status)
        self.assertEqual([call.args[1] for call in drawing.return_value.text.call_args_list], ["1", "3"])
        self.assertTrue((out / "overview.png").is_file())
        self.assertFalse((out / "slide-02.png").exists())
        self.assertEqual(unrelated.read_bytes(), b"unrelated work")

    def test_all_slides_missing_removes_old_managed_outputs(self):
        out = self.folder / "preview"
        self.assertEqual(self.run_preview(output=out)[0], 0)
        self.assertNotEqual(self.run_preview(output=out, missing=(1, 2, 3))[0], 0)
        self.assertEqual(list(out.iterdir()), [])

    def test_windows_reports_outline_fallback_without_creating_preview(self):
        with patch.object(preview.sys, "platform", "win32"), redirect_stdout(io.StringIO()) as status:
            self.assertEqual(preview.main([str(self.deck)]), 3)
        self.assertIn("deck.py --outline", status.getvalue())
        self.assertFalse((self.folder / "preview").exists())


if __name__ == "__main__":
    unittest.main()
