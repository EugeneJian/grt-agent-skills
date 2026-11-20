#!/usr/bin/env python3
"""Render every slide of a .pptx to PNG and one overview image, without opening PowerPoint or Keynote.

    python preview.py deck.pptx [--out preview] [--size 1280]

macOS only: each slide is saved as a one-slide copy and drawn by Quick Look (qlmanage), which needs no
permission prompts. Elsewhere it explains that no preview is available; check the deck with deck.py --outline.
The default output is preview/<deck stem>/ beside the deck. A partial preview exits with status 1.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

try:
    from PIL import Image, ImageDraw
    from pptx import Presentation
    from pptx.opc.constants import RELATIONSHIP_TYPE as RT
except ImportError:
    sys.exit("python-pptx is not installed. Run: <your venv>/bin/python -m pip install python-pptx==1.0.2")


def single_slide(deck: Path, index: int, target: Path) -> None:
    """Save a copy of `deck` that keeps only slide `index` (0-based), without its speaker notes.

    Quick Look (macOS 27) stalls on python-pptx notes pages, and a preview has no use for notes.
    """
    prs = Presentation(str(deck))
    slide_ids = list(prs.slides._sldIdLst)
    for position, slide_id in enumerate(slide_ids):
        if position != index:
            prs.part.drop_rel(slide_id.rId)
            prs.slides._sldIdLst.remove(slide_id)
    slide = prs.slides[0]
    for rel_id, rel in list(slide.part.rels.items()):
        if rel.reltype == RT.NOTES_SLIDE:
            slide.part.drop_rel(rel_id)
    prs.save(str(target))


def render(copy: Path, folder: Path, size: int) -> Path | None:
    try:
        subprocess.run(["qlmanage", "-t", "-s", str(size), "-o", str(folder), str(copy)],
                       capture_output=True, timeout=20, check=False)
    except subprocess.TimeoutExpired:
        return None
    picture = folder / f"{copy.name}.png"
    return picture if picture.is_file() else None


def overview(pictures: list[tuple[int, Path]], target: Path, columns: int = 3) -> None:
    thumbs = []
    for number, picture in pictures:
        with Image.open(picture) as image:
            thumbs.append((number, image.convert("RGB").resize((480, round(480 * image.height / image.width)))))
    width, height, gap = 480, max(thumb.height for _, thumb in thumbs), 16
    rows = math.ceil(len(thumbs) / columns)
    sheet = Image.new("RGB", (columns * width + (columns + 1) * gap, rows * (height + 28) + (rows + 1) * gap),
                      "#E2E8F0")
    draw = ImageDraw.Draw(sheet)
    for index, (number, thumb) in enumerate(thumbs):
        row, column = divmod(index, columns)
        x, y = gap + column * (width + gap), gap + row * (height + 28 + gap)
        sheet.paste(thumb, (x, y + 28))
        draw.text((x, y + 6), str(number), fill="#334155")
    sheet.save(target)


def clear_generated_images(out: Path) -> None:
    """Remove the preview's reserved filenames while preserving unrelated files."""
    for path in out.iterdir():
        if path.name == "overview.png" or re.fullmatch(r"slide-(?:0[1-9]|[1-9][0-9]+)\.png", path.name):
            if path.is_file() or path.is_symlink():
                path.unlink()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("deck", type=Path)
    parser.add_argument("--out", type=Path, help="image output folder (default: preview/<deck stem>/ beside the deck)")
    parser.add_argument("--size", type=int, default=1280, help="width of each slide image in pixels")
    args = parser.parse_args(argv)
    if sys.platform != "darwin" or not shutil.which("qlmanage"):
        print("No slide preview on this system (it needs macOS Quick Look). Check the text with: "
              "deck.py --outline " + str(args.deck))
        return 3
    deck = args.deck.resolve()
    out = (args.out or deck.parent / "preview" / deck.stem).resolve()
    count = len(Presentation(str(deck)).slides)
    out.mkdir(parents=True, exist_ok=True)
    clear_generated_images(out)
    pictures, missing = [], []
    with tempfile.TemporaryDirectory(prefix=".pptx-preview-", dir=out) as temporary:
        folder = Path(temporary)
        for index in range(count):
            copy = folder / f"slide-{index + 1:02d}.pptx"
            single_slide(deck, index, copy)
            picture = render(copy, folder, args.size)
            if picture is None:
                missing.append(index + 1)
                continue
            target = out / f"slide-{index + 1:02d}.png"
            picture.replace(target)
            pictures.append((index + 1, target))
    if pictures:
        overview(pictures, out / "overview.png")
        label = "partial overview" if missing else "overview"
        print(f"{label}: {out / 'overview.png'}")
    for _, picture in pictures:
        print(picture)
    if missing:
        print(f"Quick Look could not draw slide(s): {', '.join(map(str, missing))}")
    return 0 if pictures and not missing else 1


if __name__ == "__main__":
    sys.exit(main())
