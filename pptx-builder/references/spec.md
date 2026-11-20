# deck.json

One object with a `slides` list. Everything else is optional.

```json
{
  "title": "智慧储能解决方案",
  "footer": "智慧储能解决方案 · 产品部",
  "theme": {"primary": "#2563EB", "accent": "#F59E0B"},
  "slides": [{"layout": "cover", "title": "智慧储能解决方案", "subtitle": "工商业场景"}]
}
```

| Key | Meaning |
|---|---|
| `title` | The deck's name; shown in the footer when `footer` is not given |
| `footer` | Footer text on content slides (bottom left); page numbers are added bottom right |
| `theme` | Colours and fonts, see below |
| `slides` | The slides, in order |

Every slide may also have `notes`: speaker notes, shown in PowerPoint's presenter view.

## Layouts

| `layout` | Required | Optional | Use for |
|---|---|---|---|
| `cover` | `title` | `subtitle`, `note` (presenter, date) | First slide |
| `agenda` | `items` (list of strings) | `title` (default 目录) | Up to 10 parts; two columns above 5 |
| `section` | `title` | `number` (e.g. "01"), `subtitle` | Start of a part |
| `bullets` | `title`, `bullets` | `lead` (one highlighted sentence) | A message with its reasons |
| `two_column` | `title`, `left`, `right` | - | Comparisons, before/after |
| `kpi` | `title`, `items` (1-4) | `takeaway` | Headline numbers |
| `chart` | `title`, `chart` | `takeaway`, `source` | Trends, shares, rankings |
| `table` | `title`, `columns`, `rows` | `source` | Specs, options, plans |
| `timeline` | `title`, `steps` (2-6) | - | Plans, history, process |
| `image` | `title`, `image` (path) | `caption` | Photos, diagrams, generated charts |
| `closing` | - | `title` (default 谢谢), `subtitle` | Last slide |

Field shapes:

- `bullets`: strings, or `{"text": "...", "level": 1}` for an indented sub-point.
- `left` / `right`: `{"heading": "...", "bullets": [...]}`.
- `kpi` items: `{"value": "18%", "label": "用电成本下降", "note": "按两充两放测算"}`.
- `chart`: `{"type": "column", "categories": [...], "series": [{"name": "...", "values": [...]}]}`.
  Types: `column`, `bar` (horizontal), `line`, `pie`, `stacked_column`, `stacked_bar`. Each series needs one
  value per category. `pie` takes one series of shares (0.52 or 52 both work; labels show percentages).
  Optional `"labels": true|false` (default: on for one series with 12 categories or fewer),
  `"number_format": "0.0"`, and the value axis `"axis_min"`, `"axis_max"`, `"axis_step"` (e.g. 0, 1500, 500)
  when the automatic range squashes the bars.
- `takeaway` (chart, kpi): a string, or a list of short points shown beside the chart.
- `table`: `columns` is the header row; every row in `rows` has the same number of cells. Keep it to about
  8 rows and 6 columns; the script warns beyond 10 × 7.
- `timeline` steps: `{"when": "第 1 周", "title": "现场勘查", "text": "负荷与配电条件"}`.
- `image`: absolute, or relative to the folder of `deck.json`. It is scaled to fit, keeping its shape.

## Theme

| Key | Default | |
|---|---|---|
| `primary` | `#2563EB` | Titles' bar, highlights, first chart series |
| `accent` | `#F59E0B` | Second series, cover rule, section numbers |
| `text` / `muted` | `#0F172A` / `#64748B` | Body and secondary text |
| `panel` / `background` | `#F1F5F9` / `#FFFFFF` | Card fills, page |
| `font` | `Microsoft YaHei` | Chinese text (installed on Windows; PowerPoint for Mac substitutes) |
| `latin_font` | `Arial` | Letters and digits |

Colours are `#RRGGBB`. Use a company's colours only when the user gives them.

## Templates

`--template company.pptx` builds on that file: its slide size, masters and background are kept; its
existing slides are not. Text still uses the `font`, `latin_font` and colours above, so set `theme` to the
company's fonts and colours when they differ. The layouts above are drawn on its emptiest slide layout, scaled to
its size, so check the preview: a 4:3 template stretches the 16:9 geometry.

## Output

`deck.py` prints one line per slide, then `WARNING:` lines for text that may not fit and tables that are
too large, then the path written. Exit code 2 reports an input or output error. The deck is assembled in
a temporary location and published under a new file name. If that name already exists, use a new versioned
name for the output. `--outline` lists the existing deck's slide structure.
