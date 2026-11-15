# Writing a good deck

## Storylines

Pick one and adapt it; titles carry the message.

- **Solution pitch** (方案介绍): cover → agenda → problem (bullets + kpi) → solution (two_column / image) →
  how it works (timeline or table) → results (chart + kpi) → plan (timeline) → closing.
- **Status report** (工作汇报): cover → summary (kpi) → progress (table / timeline) → issues (bullets) →
  next steps (bullets) → closing.
- **Data review** (数据分析): cover → key finding (kpi) → one chart per finding (chart with takeaway) →
  recommendations (bullets) → closing.

## Slide writing

- Title = the conclusion: 「夏季节省电费最多」, not 「月度节省电费」.
- One idea per slide; when a slide needs more than 6 bullets, split it.
- Numbers: unit, period and source on the slide (`source`). Never round away the meaning.
- Mix layouts: no more than three `bullets` slides in a row.
- Chinese decks: Chinese punctuation, a space between Chinese and numbers with units (「18 万元」).
- Speaker notes hold what the presenter says; slides hold what the audience reads.

## Checking the preview

`preview.py` draws each slide with macOS Quick Look. Known differences from PowerPoint:

- Pie charts appear in one colour without percentage labels; PowerPoint shows the colours and labels.
- Number formats on data labels may be ignored, and axis ranges can differ.
- Where Microsoft YaHei is not installed, Chinese text falls back to another font.

These are preview limits, not faults in the deck. Real faults to fix: text running out of its box,
overlapping shapes, empty slides, wrong numbers.

Quick Look stalls on decks that have speaker notes, so `preview.py` renders copies without notes. For the
same reason, pressing Space on such a deck in the Finder may not show a preview; PowerPoint, WPS and
Keynote open it normally.
