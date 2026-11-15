"""Offline checks for pptx-builder: python -m unittest discover -s pptx-builder/tests -v (needs python-pptx)."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))

try:
    from pptx import Presentation
    from pptx.oxml.ns import qn
    from pptx.util import Inches
except ImportError:                                          # The CI installs it; say why nothing ran.
    raise unittest.SkipTest("python-pptx is not installed")

import deck as builder
import preview

EXAMPLE = json.loads((SKILL / "references" / "example.json").read_text(encoding="utf-8"))


class DeckTests(unittest.TestCase):
    def setUp(self):
        folder = TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def build(self, spec, **options):
        target = self.folder / "deck.pptx"
        made = builder.Deck(spec, **options)
        made.build()
        made.save(target)
        return Presentation(str(target)), made

    def test_the_example_uses_every_layout_and_builds(self):
        self.assertTrue(set(builder.LAYOUTS) - {"image"} <= {slide["layout"] for slide in EXAMPLE["slides"]})
        prs, made = self.build(EXAMPLE)
        self.assertEqual(len(prs.slides), len(EXAMPLE["slides"]))
        self.assertEqual((prs.slide_width, prs.slide_height), (12192000, 6858000))     # 16:9
        self.assertEqual(made.warnings, [])

    def test_charts_are_native_and_editable(self):
        prs, _ = self.build(EXAMPLE)
        charts = [shape.chart for slide in prs.slides for shape in slide.shapes if shape.has_chart]
        self.assertEqual(len(charts), 2)
        self.assertEqual(list(charts[0].plots[0].categories), ["1月", "2月", "3月", "4月", "5月", "6月"])
        self.assertEqual(list(charts[0].plots[0].series[0].values), [12.5, 11.8, 14.2, 15.1, 16.4, 18.0])

    def test_the_value_axis_can_be_set_so_bars_are_not_squashed(self):
        spec = {"slides": [{"layout": "chart", "title": "电费", "chart": {
            "type": "column", "categories": ["1月", "2月"], "series": [{"name": "元", "values": [980, 1240]}],
            "axis_min": 0, "axis_max": 1500, "axis_step": 500}}]}
        prs, _ = self.build(spec)
        chart = next(shape.chart for shape in prs.slides[0].shapes if shape.has_chart)
        axis = chart.value_axis
        self.assertEqual((axis.minimum_scale, axis.maximum_scale, axis.major_unit), (0, 1500, 500))

    def test_tables_notes_and_chinese_fonts(self):
        prs, _ = self.build(EXAMPLE)
        table = next(shape.table for slide in prs.slides for shape in slide.shapes if shape.has_table)
        self.assertEqual(table.cell(0, 1).text, "方案 A")
        self.assertEqual(table.cell(4, 3).text, "3.9 年")
        self.assertIn("三个问题", prs.slides[0].notes_slide.notes_text_frame.text)
        title = next(shape for shape in prs.slides[0].shapes if shape.has_text_frame
                     and shape.text_frame.text == "智慧储能解决方案")
        run = title.text_frame.paragraphs[0].runs[0]
        self.assertEqual(run._r.rPr.find(qn("a:ea")).get("typeface"), "Microsoft YaHei")
        self.assertEqual(run.font.name, "Arial")

    def test_text_that_cannot_fit_is_reported_and_normal_text_is_not(self):
        crowded = {"slides": [{"layout": "bullets", "title": "太多",
                               "bullets": ["这是一条非常长的要点，用来测试文字是否会超出文本框的范围" * 2] * 9}]}
        _, made = self.build(crowded)
        self.assertEqual(len(made.warnings), 1)
        self.assertIn("slide 1", made.warnings[0])
        _, made = self.build({"slides": [{"layout": "bullets", "title": "刚好", "bullets": ["一", "二", "三"]}]})
        self.assertEqual(made.warnings, [])

    def test_mistakes_in_the_json_are_explained(self):
        for spec, message in (({"slides": []}, "slides"), ({"slides": [{"layout": "poster"}]}, "layout must be"),
                              ({"slides": [{"layout": "bullets", "bullets": ["a"]}]}, '"title"'),
                              ({"slides": [{"layout": "kpi", "title": "x", "items": [{"value": 1, "label": "a"}] * 5}]},
                               "1 to 4"),
                              ({"slides": [{"layout": "chart", "title": "x", "chart": {
                                  "categories": ["a", "b"], "series": [{"name": "s", "values": [1]}]}}]},
                               "one value per category"),
                              ({"theme": {"primary": "blue"}, "slides": [{"layout": "closing"}]}, "colour")):
            with self.subTest(message=message), self.assertRaisesRegex(builder.SpecError, message):
                self.build(spec)

    def test_images_are_found_beside_the_json(self):
        from PIL import Image

        Image.new("RGB", (400, 200), "#2563EB").save(self.folder / "chart.png")
        spec = {"slides": [{"layout": "image", "title": "图", "image": "chart.png", "caption": "说明"}]}
        prs, _ = self.build(spec, base=self.folder)
        self.assertEqual(sum(shape.shape_type == 13 for shape in prs.slides[0].shapes), 1)

    def test_a_template_lends_its_size_and_keeps_none_of_its_slides(self):
        template = Presentation()
        template.slide_width, template.slide_height = Inches(10), Inches(7.5)          # 4:3
        template.slides.add_slide(template.slide_layouts[0])
        template.save(str(self.folder / "template.pptx"))
        prs, _ = self.build({"slides": [{"layout": "closing"}]}, template=self.folder / "template.pptx")
        self.assertEqual((prs.slide_width, len(prs.slides)), (Inches(10), 1))
        self.assertEqual(len(prs.slides[0].placeholders), 0)

    def test_the_command_line_writes_the_deck_and_reports_problems(self):
        source = self.folder / "deck.json"
        source.write_text(json.dumps(EXAMPLE, ensure_ascii=False), encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(builder.main([str(source), str(self.folder / "out.pptx")]), 0)
        self.assertEqual(len(builder.outline(self.folder / "out.pptx")), len(EXAMPLE["slides"]))
        source.write_text('{"slides": [{"layout": "poster"}]}', encoding="utf-8")
        with redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(builder.main([str(source), str(self.folder / "bad.pptx")]), 2)
        self.assertIn("layout must be", errors.getvalue())
        self.assertFalse((self.folder / "bad.pptx").exists())


class PreviewTests(unittest.TestCase):
    def test_a_preview_copy_keeps_one_slide_and_drops_its_notes(self):
        with TemporaryDirectory() as folder:
            folder = Path(folder)
            made = builder.Deck(EXAMPLE)
            made.build()
            made.save(folder / "deck.pptx")
            preview.single_slide(folder / "deck.pptx", 0, folder / "one.pptx")
            copy = Presentation(str(folder / "one.pptx"))
            self.assertEqual(len(copy.slides), 1)
            self.assertFalse(copy.slides[0].has_notes_slide)
            self.assertIn("智慧储能解决方案", [shape.text_frame.text for shape in copy.slides[0].shapes
                                               if shape.has_text_frame])


if __name__ == "__main__":
    unittest.main()
