---
name: pptx-builder
description: Make PowerPoint (.pptx) presentations - 制作 PPT、演示文稿、汇报、路演、方案介绍. Plan the story, describe each slide in JSON, build an editable 16:9 deck with native charts, tables and Chinese fonts, then preview every slide without opening PowerPoint. Not for Feishu online slides (use lark-slides).
---

# pptx-builder

Turns a request like 「帮我做一份储能方案介绍 PPT」 into an editable `.pptx`: you write the content as JSON,
`scripts/deck.py` draws it with a consistent design, `scripts/preview.py` shows you every slide.

## Set up once

Work in a folder named after the deck inside your working directory. Use a virtual environment there,
never the system Python or another project's environment:

```sh
python3 -m venv .venv                       # Windows: py -m venv .venv
.venv/bin/python -m pip install python-pptx==1.0.2      # Windows: .venv\Scripts\python
```

`SKILL_DIR` below is the folder that holds this file.

## Workflow

1. **Clarify briefly**, only what is missing: audience and goal, number of slides (default 8-12),
   language, and whether a company `.pptx` template must be used. Do not ask what the user already said.
2. **Outline**: one line per slide - its message, not its topic. For more than 12 slides, show the
   outline and wait for agreement before building.
3. **Write `deck.json`** in the deck folder. Read [references/spec.md](references/spec.md) for the layouts
   and fields; copy from [references/example.json](references/example.json).
4. **Build**: `.venv/bin/python SKILL_DIR/scripts/deck.py deck.json "<标题>.pptx"`
   (add `--template company.pptx` to use a template's masters and size).
   Fix every `WARNING`: shorten the text or split the slide, then build again.
5. **Preview** (macOS): `.venv/bin/python SKILL_DIR/scripts/preview.py "<标题>.pptx"` writes
   `preview/slide-NN.png` and `preview/overview.png`. If you can see images, read `overview.png` and fix
   what looks wrong. Elsewhere, check the text with `deck.py --outline "<标题>.pptx"`.
6. **Deliver**: give the absolute path of the `.pptx`, show `overview.png` as
   `![预览](/absolute/path/preview/overview.png)`, and list what is in the folder. Keep `deck.json`:
   later edits change the JSON and rebuild.

## Rules

- **Never invent numbers.** Use the user's data. Without it, write 「示例数据」 in the slide title or
  source line and say so in your reply.
- One message per slide; at most 6 bullets, each about 20 Chinese characters or 12 English words.
  Put details in `notes` (speaker notes), not on the slide.
- Do not drive PowerPoint, Keynote or WPS with AppleScript, COM or `open`: they ask for permissions,
  hang, and leave lock files. The scripts need neither.
- Never overwrite an existing deck: add a version (`v2`) to the new file name.
- Images only from the user or made by you (e.g. a matplotlib chart); give their paths in the JSON.
- Charts are native PowerPoint charts, so the user can edit the data. Prefer them to pictures of charts.

## More

- [references/spec.md](references/spec.md) - every layout and field, colours, fonts, templates
- [references/design.md](references/design.md) - storylines, slide writing, and known preview limits
