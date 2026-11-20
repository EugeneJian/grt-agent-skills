---
name: pptx-builder
description: 制作可编辑的本地 PowerPoint（.pptx），适用于工作汇报、方案介绍、数据复盘和路演。按受众与结论规划每页，用 JSON 生成原生文字、图表和表格，可沿用公司母版并逐页检查。飞书在线幻灯片使用 lark-slides。
---

# PPTX Builder

用现有版式生成可编辑的 `.pptx`。每页先确定要传达的结论，再选能表达证据关系的版式。

## 制作

1. **定目标。** 只问会影响交付的信息，包括受众要做的决定、投屏还是阅读、语言、页数和模板要求。页数未指定时可按内容安排 8–12 页，并说明必要假设。
2. **排故事。** 提纲每页写一句结论、支撑证据和表达关系。用对比、趋势、流程、关键数字等关系选版式。设计与验收细节见[逐页设计](references/design.md)。
3. **写源稿。** 在任务目录写 `deck.json`。按[规格](references/spec.md)和[示例](references/example.json)填写字段，保留演讲者备注、图片和数据出处。相对图片路径以 JSON 所在目录为准。
4. **生成。** 用项目虚拟环境的 Python 执行 `scripts/deck.py deck.json "<标题>_v1.pptx"`。要沿用公司母版和页面尺寸时加 `--template company.pptx`。需在原稿保留已有页面并局部修改时，使用宿主已有的原稿编辑工具并另存版本。
5. **校验。** 检查构建警告，优先删减、拆页或调整构图。在 macOS 用 `scripts/preview.py "<标题>_v1.pptx"` 生成逐页图，核对页数、总览和每一页。其他平台可用 `scripts/deck.py --outline "<标题>_v1.pptx"` 核对结构，并如实说明视觉验证范围。
6. **交付。** 给出 PPT 和 `deck.json` 的路径。只提供实际生成并检查过的预览，记录缺页或未验证项。续改使用同一源稿，并将新 PPT 存为新版本。

## 环境

脚本路径相对于本 `SKILL.md`。优先复用任务工作区里已安装 `python-pptx==1.0.2` 的虚拟环境。
缺少时在任务目录建立 `.venv`（macOS/Linux 用 `python3 -m venv .venv`，Windows 用 `py -m venv .venv`），
再用 `.venv/bin/python` 或 `.venv\Scripts\python.exe` 执行 `-m pip install python-pptx==1.0.2`。
macOS 预览使用系统 Quick Look，制作和校验均通过命令行执行。
