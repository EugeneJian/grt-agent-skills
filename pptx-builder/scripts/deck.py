#!/usr/bin/env python3
"""Build an editable 16:9 PowerPoint deck from a JSON description.

    python deck.py deck.json out.pptx          build; prints each slide and any text that may not fit
    python deck.py --outline out.pptx          list the slides and text of an existing deck

The JSON format is described in ../references/spec.md. Needs python-pptx (pip install python-pptx==1.0.2).
"""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

try:
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.dml.color import RGBColor
    from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
    from pptx.enum.shapes import MSO_SHAPE
    from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
    from pptx.oxml.ns import qn
    from pptx.util import Emu, Pt
except ImportError:                                         # Say how to fix it, not just that it failed.
    sys.exit("python-pptx is not installed. Run: <your venv>/bin/python -m pip install python-pptx==1.0.2")


class SpecError(ValueError):
    pass


WIDE = (13.333, 7.5)                                        # Inches; geometry below is drawn for 16:9.
THEME = {
    "primary": "#2563EB", "accent": "#F59E0B", "text": "#0F172A", "muted": "#64748B",
    "panel": "#F1F5F9", "background": "#FFFFFF",
    "font": "Microsoft YaHei",                              # East Asian text; PowerPoint on Mac falls back to PingFang.
    "latin_font": "Arial",
}
SERIES = ("primary", "accent", "#14B8A6", "#8B5CF6", "#EF4444", "#64748B")
LAYOUTS = ("cover", "agenda", "section", "bullets", "two_column", "kpi", "chart", "table", "timeline", "image",
           "closing")
CHARTS = {"column": XL_CHART_TYPE.COLUMN_CLUSTERED, "bar": XL_CHART_TYPE.BAR_CLUSTERED,
          "line": XL_CHART_TYPE.LINE_MARKERS, "pie": XL_CHART_TYPE.PIE,
          "stacked_column": XL_CHART_TYPE.COLUMN_STACKED, "stacked_bar": XL_CHART_TYPE.BAR_STACKED}


def _rgb(value: str) -> RGBColor:
    try:
        return RGBColor.from_string(value.lstrip("#").upper())
    except (ValueError, AttributeError):
        raise SpecError(f"not a colour like #2563EB: {value!r}") from None


class Deck:
    def __init__(self, spec: dict, template: Path | None = None, base: Path | None = None):
        """`base` is where relative image paths start: the folder of the JSON file."""
        if not isinstance(spec, dict) or not isinstance(spec.get("slides"), list) or not spec["slides"]:
            raise SpecError('the JSON needs a non-empty "slides" list')
        self.spec = spec
        self.theme = {**THEME, **(spec.get("theme") or {})}
        self.color = {name: _rgb(value) for name, value in self.theme.items() if name not in ("font", "latin_font")}
        self.prs = Presentation(str(template)) if template else Presentation()
        if template:
            for slide_id in list(self.prs.slides._sldIdLst):  # Keep the template's design, not its slides.
                self.prs.part.drop_rel(slide_id.rId)
                self.prs.slides._sldIdLst.remove(slide_id)
        else:
            self.prs.slide_width, self.prs.slide_height = Emu(12192000), Emu(6858000)
        self.sx = self.prs.slide_width / 914400 / WIDE[0]
        self.sy = self.prs.slide_height / 914400 / WIDE[1]
        layouts = list(self.prs.slide_layouts)
        self.blank = min(layouts, key=lambda layout: len(layout.placeholders))
        self.warnings: list[str] = []
        self.number = 0
        self.base = base or Path.cwd()

    # Drawing helpers --------------------------------------------------------------------------------

    def box(self, x, y, w, h):
        return (Emu(round(x * self.sx * 914400)), Emu(round(y * self.sy * 914400)),
                Emu(round(w * self.sx * 914400)), Emu(round(h * self.sy * 914400)))

    def rect(self, slide, x, y, w, h, color, shape=MSO_SHAPE.RECTANGLE):
        item = slide.shapes.add_shape(shape, *self.box(x, y, w, h))
        item.fill.solid()
        item.fill.fore_color.rgb = self.color[color] if color in self.color else _rgb(color)
        item.line.fill.background()
        item.shadow.inherit = False
        return item

    def text(self, slide, x, y, w, h, paragraphs, size, color="text", *, bold=False, align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP, bullets=False, check=True):
        """`paragraphs`: a string, or a list of strings / {"text", "level"}; level 1 is indented and smaller."""
        items = [paragraphs] if isinstance(paragraphs, str) else list(paragraphs or ())
        bounds = self.box(x, y, w, h)
        frame = slide.shapes.add_textbox(*bounds).text_frame
        frame.word_wrap, frame.auto_size, frame.vertical_anchor = True, MSO_AUTO_SIZE.NONE, anchor
        frame.margin_left = frame.margin_right = Emu(45720)
        frame.margin_top = frame.margin_bottom = Emu(27432)
        text_width = bounds[2].inches - frame.margin_left.inches - frame.margin_right.inches
        box_height = bounds[3].pt
        needed = 0.0
        for index, item in enumerate(items):
            text, level = (item, 0) if isinstance(item, str) else (str(item.get("text", "")), int(item.get("level", 0)))
            paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
            paragraph.alignment = align
            point = size if level == 0 else max(size - 4, 10)
            spacing = point * (0.45 if bullets else 0.15)
            paragraph.space_after = Pt(spacing)
            indent = 0.3 * level if bullets else 0
            if bullets:
                self.run(paragraph, ("•" if level == 0 else "–") + "  ", point, "primary" if level == 0 else "muted")
                paragraph.level = 0
                if indent:
                    paragraph._p.get_or_add_pPr().set("marL", str(int(indent * 914400)))
            self.run(paragraph, text, point, color, bold=bold)
            needed += _height(("•  " if bullets else "") + text, point, text_width - indent) + spacing
        if check and needed > box_height * 1.02:
            self.warnings.append(f"slide {self.number}: text may not fit (about {needed / box_height:.0%} of its box): "
                                 f"{_preview(items)}")
        return frame

    def run(self, paragraph, text, size, color, *, bold=False):
        run = paragraph.add_run()
        run.text = text
        run.font.size, run.font.bold = Pt(size), bold
        run.font.color.rgb = self.color[color] if color in self.color else _rgb(color)
        run.font.name = self.theme["latin_font"]
        latin = run._r.get_or_add_rPr().find(qn("a:latin"))
        latin.addnext(latin.makeelement(qn("a:ea"), {"typeface": self.theme["font"]}))   # Chinese glyphs
        return run

    def title(self, slide, text):
        self.rect(slide, 0.7, 0.62, 0.08, 0.62, "primary")
        self.text(slide, 0.95, 0.5, 11.6, 0.9, text, 28, bold=True, anchor=MSO_ANCHOR.MIDDLE)

    def footer(self, slide):
        footer = self.spec.get("footer") or self.spec.get("title") or ""
        if footer:
            self.text(slide, 0.7, 6.95, 9, 0.35, footer, 10, "muted", check=False)
        self.text(slide, 11.6, 6.95, 1.0, 0.35, str(self.number), 10, "muted", align=PP_ALIGN.RIGHT, check=False)

    # Layouts ----------------------------------------------------------------------------------------

    def cover(self, slide, s):
        self.rect(slide, 0, 0, 0.35, 7.5, "primary")
        self.rect(slide, 0.95, 2.35, 1.2, 0.08, "accent")
        self.text(slide, 0.95, 2.55, 11.4, 1.6, _need(s, "title"), 40, bold=True, anchor=MSO_ANCHOR.TOP)
        self.text(slide, 0.95, 4.2, 11.4, 0.9, s.get("subtitle", ""), 20, "muted")
        self.text(slide, 0.95, 6.3, 11.4, 0.5, s.get("note", ""), 14, "muted")

    def agenda(self, slide, s):
        self.title(slide, s.get("title", "目录"))
        items = _need(s, "items")
        columns = 2 if len(items) > 5 else 1
        per = math.ceil(len(items) / columns)
        for index, item in enumerate(items):
            column, row = divmod(index, per)
            x, y = 1.0 + column * 5.9, 1.75 + row * 0.95
            self.rect(slide, x, y, 0.62, 0.62, "primary", MSO_SHAPE.OVAL)
            self.text(slide, x, y, 0.62, 0.62, f"{index + 1:02d}", 16, "background", bold=True,
                      align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, check=False)
            self.text(slide, x + 0.85, y - 0.05, 4.9, 0.72, item, 20, anchor=MSO_ANCHOR.MIDDLE)
        self.footer(slide)

    def section(self, slide, s):
        self.rect(slide, 0, 0, 13.333, 7.5, "primary")
        self.text(slide, 0.95, 1.9, 4, 1.4, s.get("number", ""), 66, "accent", bold=True, check=False)
        self.text(slide, 0.95, 3.35, 11.4, 1.2, _need(s, "title"), 40, "background", bold=True)
        self.text(slide, 0.95, 4.6, 11.4, 0.8, s.get("subtitle", ""), 18, "panel")

    def bullets(self, slide, s):
        self.title(slide, _need(s, "title"))
        top = 1.65
        if s.get("lead"):
            self.rect(slide, 0.95, top, 11.4, 0.8, "panel")
            self.text(slide, 1.15, top, 11.0, 0.8, s["lead"], 18, "primary", bold=True, anchor=MSO_ANCHOR.MIDDLE)
            top += 1.05
        self.text(slide, 0.95, top, 11.4, 6.75 - top, _need(s, "bullets"), 20, bullets=True)
        self.footer(slide)

    def two_column(self, slide, s):
        self.title(slide, _need(s, "title"))
        for index, side in enumerate((_need(s, "left"), _need(s, "right"))):
            x = 0.95 + index * 5.85
            self.rect(slide, x, 1.65, 5.55, 5.05, "panel")
            self.text(slide, x + 0.3, 1.85, 4.95, 0.6, side.get("heading", ""), 20, "primary", bold=True)
            self.text(slide, x + 0.3, 2.55, 4.95, 4.0, side.get("bullets", []), 16, bullets=True)
        self.footer(slide)

    def kpi(self, slide, s):
        self.title(slide, _need(s, "title"))
        items = _need(s, "items")
        if not 1 <= len(items) <= 4:
            raise SpecError(f"slide {self.number}: kpi takes 1 to 4 items")
        width = (11.4 - 0.3 * (len(items) - 1)) / len(items)
        for index, item in enumerate(items):
            x = 0.95 + index * (width + 0.3)
            self.rect(slide, x, 2.0, width, 3.6, "panel")
            self.rect(slide, x, 2.0, width, 0.08, "primary")
            self.text(slide, x + 0.25, 2.35, width - 0.5, 1.3, str(_need(item, "value")), 40, "primary", bold=True)
            self.text(slide, x + 0.25, 3.7, width - 0.5, 0.7, _need(item, "label"), 16, bold=True)
            self.text(slide, x + 0.25, 4.4, width - 0.5, 1.0, item.get("note", ""), 12, "muted")
        if s.get("takeaway"):
            self.text(slide, 0.95, 5.9, 11.4, 0.7, s["takeaway"], 16, "muted")
        self.footer(slide)

    def chart(self, slide, s):
        self.title(slide, _need(s, "title"))
        spec = _need(s, "chart")
        kind = spec.get("type", "column")
        if kind not in CHARTS:
            raise SpecError(f"slide {self.number}: chart type must be one of {', '.join(CHARTS)}")
        data = CategoryChartData()
        data.categories = _need(spec, "categories")
        series = _need(spec, "series")
        for item in series:
            values = _need(item, "values")
            if len(values) != len(data.categories):
                raise SpecError(f"slide {self.number}: series {item.get('name')!r} needs one value per category")
            data.add_series(item.get("name", ""), values)
        width = 7.6 if s.get("takeaway") else 11.4
        chart = slide.shapes.add_chart(CHARTS[kind], *self.box(0.95, 1.65, width, 5.05), data).chart
        chart.font.size, chart.font.name = Pt(12), self.theme["latin_font"]
        chart.has_legend = kind == "pie" or len(series) > 1
        if chart.has_legend:
            chart.legend.position, chart.legend.include_in_layout = XL_LEGEND_POSITION.BOTTOM, False
        plot = chart.plots[0]
        colors = [self.color[name] if name in self.color else _rgb(name) for name in SERIES]
        if kind == "pie":
            for index, point in enumerate(plot.series[0].points):
                point.format.fill.solid()
                point.format.fill.fore_color.rgb = colors[index % len(colors)]
            plot.has_data_labels = True
            plot.data_labels.show_percentage, plot.data_labels.show_value = True, False
            plot.data_labels.number_format, plot.data_labels.number_format_is_linked = "0%", False
        else:
            for index, item in enumerate(plot.series):
                color = colors[index % len(colors)]
                if kind == "line":
                    item.format.line.color.rgb = color
                    item.smooth = False
                else:
                    item.format.fill.solid()
                    item.format.fill.fore_color.rgb = color
            chart.value_axis.has_major_gridlines = True
            chart.value_axis.major_gridlines.format.line.color.rgb = self.color["panel"]
            for key, attribute in (("axis_min", "minimum_scale"), ("axis_max", "maximum_scale"),
                                   ("axis_step", "major_unit")):
                if spec.get(key) is not None:
                    setattr(chart.value_axis, attribute, spec[key])
            if kind != "line":
                plot.gap_width = 80                               # Fuller bars than PowerPoint's 150.
            if spec.get("labels", len(series) == 1 and len(data.categories) <= 12):
                plot.has_data_labels = True
                plot.data_labels.font.size = Pt(11)
                if spec.get("number_format"):
                    plot.data_labels.number_format, plot.data_labels.number_format_is_linked = spec["number_format"], False
        if s.get("takeaway"):
            self.rect(slide, 8.85, 1.65, 3.5, 5.05, "panel")
            self.text(slide, 9.1, 1.9, 3.0, 4.6, s["takeaway"], 16, bullets=not isinstance(s["takeaway"], str))
        if s.get("source"):
            self.text(slide, 0.95, 6.6, 11.4, 0.35, s["source"], 10, "muted")
        self.footer(slide)

    def table(self, slide, s):
        self.title(slide, _need(s, "title"))
        columns, rows = _need(s, "columns"), _need(s, "rows")
        if any(len(row) != len(columns) for row in rows):
            raise SpecError(f"slide {self.number}: every table row needs {len(columns)} cells")
        if len(rows) > 10 or len(columns) > 7:
            self.warnings.append(f"slide {self.number}: {len(rows)} rows × {len(columns)} columns is hard to read; "
                                 "split it or keep the key rows")
        size = 14 if len(rows) <= 6 else 12
        height = min(5.0, 0.5 * (len(rows) + 1))
        table = slide.shapes.add_table(len(rows) + 1, len(columns), *self.box(0.95, 1.7, 11.4, height)).table
        for r, values in enumerate([columns, *rows]):
            for c, value in enumerate(values):
                cell = table.cell(r, c)
                cell.fill.solid()
                cell.fill.fore_color.rgb = self.color["primary"] if r == 0 else (
                    self.color["panel"] if r % 2 == 0 else self.color["background"])
                cell.text_frame.word_wrap = True
                paragraph = cell.text_frame.paragraphs[0]
                paragraph.alignment = PP_ALIGN.LEFT if c == 0 else PP_ALIGN.CENTER
                self.run(paragraph, str(value), size, "background" if r == 0 else "text", bold=r == 0)
        if s.get("source"):
            self.text(slide, 0.95, 6.6, 11.4, 0.35, s["source"], 10, "muted")
        self.footer(slide)

    def timeline(self, slide, s):
        self.title(slide, _need(s, "title"))
        steps = _need(s, "steps")
        if not 2 <= len(steps) <= 6:
            raise SpecError(f"slide {self.number}: timeline takes 2 to 6 steps")
        self.rect(slide, 0.95, 3.0, 11.4, 0.05, "muted")
        width = 11.4 / len(steps)
        for index, step in enumerate(steps):
            x = 0.95 + index * width
            self.rect(slide, x + 0.05, 2.83, 0.38, 0.38, "primary" if index < len(steps) - 1 else "accent",
                      MSO_SHAPE.OVAL)
            self.text(slide, x, 2.0, width - 0.2, 0.6, _need(step, "when"), 16, "primary", bold=True)
            self.text(slide, x, 3.45, width - 0.2, 0.7, _need(step, "title"), 16, bold=True)
            self.text(slide, x, 4.15, width - 0.2, 2.3, step.get("text", ""), 12, "muted")
        self.footer(slide)

    def image(self, slide, s):
        from PIL import Image                                 # Comes with python-pptx.

        self.title(slide, _need(s, "title"))
        path = Path(_need(s, "image")).expanduser()
        path = path if path.is_absolute() else self.base / path
        if not path.is_file():
            raise SpecError(f"slide {self.number}: image not found: {path}")
        with Image.open(path) as picture:
            ratio = picture.width / picture.height
        area_w, area_h = 11.4, 4.75 if s.get("caption") else 5.05
        w, h = (area_w, area_w / ratio) if area_w / ratio <= area_h else (area_h * ratio, area_h)
        slide.shapes.add_picture(str(path), *self.box(0.95 + (area_w - w) / 2, 1.65, w, h))
        if s.get("caption"):
            self.text(slide, 0.95, 1.75 + h, 11.4, 0.5, s["caption"], 12, "muted", align=PP_ALIGN.CENTER)
        self.footer(slide)

    def closing(self, slide, s):
        self.rect(slide, 0, 0, 13.333, 7.5, "primary")
        self.text(slide, 0.95, 2.6, 11.4, 1.4, s.get("title", "谢谢"), 48, "background", bold=True,
                  align=PP_ALIGN.CENTER)
        self.text(slide, 0.95, 4.1, 11.4, 1.0, s.get("subtitle", ""), 18, "panel", align=PP_ALIGN.CENTER)

    # Building ---------------------------------------------------------------------------------------

    def build(self) -> list[str]:
        lines = []
        for self.number, s in enumerate(self.spec["slides"], start=1):
            layout = s.get("layout") if isinstance(s, dict) else None
            if layout not in LAYOUTS:
                raise SpecError(f"slide {self.number}: layout must be one of {', '.join(LAYOUTS)}")
            slide = self.prs.slides.add_slide(self.blank)
            for placeholder in list(slide.placeholders):          # A template's empty boxes would show.
                placeholder._element.getparent().remove(placeholder._element)
            getattr(self, layout)(slide, s)
            if s.get("notes"):
                slide.notes_slide.notes_text_frame.text = s["notes"]
            lines.append(f"slide {self.number} {layout}: {s.get('title', '')}")
        return lines

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix=".pptx-builder-", dir=path.parent) as folder:
            draft = Path(folder) / "deck.pptx"
            self.prs.save(str(draft))
            windows = os.name == "nt"
            publish = os.rename if windows else os.link  # Both fail if the destination exists.
            try:
                publish(draft, path)
            except FileExistsError:
                raise SpecError(f"{path} already exists; choose a new output file name") from None
            except (OSError, NotImplementedError) as error:
                filesystem = "" if windows else " on a file system that supports hard links"
                raise SpecError(f"cannot publish {path}: {error}. Choose a writable output folder{filesystem}.") from None


def _need(item: dict, key: str):
    value = item.get(key) if isinstance(item, dict) else None
    if value in (None, "", []):
        raise SpecError(f'missing "{key}" in {json.dumps(item, ensure_ascii=False)[:120]}')
    return value


def _height(text: str, size: float, width_in: float) -> float:
    """Points a wrapped paragraph needs: CJK glyphs are about one em wide, Latin about half."""
    width = sum(size if ord(ch) > 0x2E7F else size * (0.3 if ch == " " else 0.55) for ch in text)
    lines = max(1, math.ceil(width / max(width_in * 72, 1)))
    return lines * size * 1.2


def _preview(items) -> str:
    first = items[0] if items else ""
    text = first if isinstance(first, str) else first.get("text", "")
    return (text[:30] + "…") if len(text) > 30 else text


def outline(path: Path) -> list[str]:
    prs = Presentation(str(path))
    lines = []
    for number, slide in enumerate(prs.slides, start=1):
        texts = [shape.text_frame.text.strip() for shape in slide.shapes
                 if shape.has_text_frame and shape.text_frame.text.strip()]
        kinds = sorted({"chart" for shape in slide.shapes if shape.has_chart} |
                       {"table" for shape in slide.shapes if shape.has_table} |
                       {"picture" for shape in slide.shapes if shape.shape_type == 13})
        notes = slide.has_notes_slide and slide.notes_slide.notes_text_frame.text.strip()
        lines.append(f"{number}. " + " | ".join(text.replace("\n", " / ")[:80] for text in texts[:4])
                     + (f"  [{', '.join(kinds)}]" if kinds else "") + ("  [notes]" if notes else ""))
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("source", type=Path, help="deck.json to build, or a .pptx with --outline")
    parser.add_argument("output", type=Path, nargs="?", help="the .pptx to write")
    parser.add_argument("--template", type=Path, help="a .pptx whose slide masters and size to use")
    parser.add_argument("--outline", action="store_true", help="list the slides of an existing .pptx")
    args = parser.parse_args(argv)
    if args.outline:
        print("\n".join(outline(args.source)))
        return 0
    if args.output is None or args.output.suffix.lower() != ".pptx":
        parser.error("give the .pptx file to write")
    try:
        spec = json.loads(args.source.read_text(encoding="utf-8"))
        deck = Deck(spec, args.template, args.source.resolve().parent)
        lines = deck.build()
        deck.save(args.output)
    except (SpecError, json.JSONDecodeError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    for warning in deck.warnings:
        print(f"WARNING: {warning}")
    print(f"wrote {args.output.resolve()} ({len(lines)} slides)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
