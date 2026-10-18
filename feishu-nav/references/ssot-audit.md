# SSOT 架构与拓扑审计

共享 skill 的单一真源为 `~/.agents/skills/`；本 skill 的真实目录是其直接子目录 `feishu-nav/`。真源至少包含一个非隐藏 skill 目录，每个这样的目录均须真实且含 `SKILL.md`；真源和工具目录的路径不得通过软链别名。

## 规则

- `~/.claude/skills`、`~/.codex/skills` 默认必须有指向每个同名共享 skill 真身的链接，真实副本即使内容相同也不合格
- pi 直接扫描真源，`~/.pi/agent/skills` 可不存在；cc-switch 已退役，`~/.cc-switch/skills` 也可不存在。两者若保留条目，仍检查其归属及链接目标
- 顶层点开头项（如 `.git`、Codex 管理的 `.system`）是元数据边界，排除检查；不要在其中放个人 skill。其他非隐藏工具专属 skill 必须用可重复的 `--tool-specific TOOL:SKILL` 明确声明，名称须是非隐藏的单个目录名，该工具中的实际目录须含 `SKILL.md`，不能与真源或其他工具重名
- `--require-tool TOOL` 可额外要求某个工具完整覆盖共享链接；`--home PATH` 用于隔离测试

## 运行

```bash
# 只读拓扑审计：安装器更新、新增 skill 或修改链接后运行
python3 ~/.agents/skills/feishu-nav/scripts/skill-ssot-audit.py
```

审计只检测、不修复，也不验证 CLI 安装、认证、飞书权限或各工具实际加载。遇到真实副本/错误链接时停止，先比对并备份，再由本人决定如何处理；不要自动删除、移动或覆盖。新机安装与安全链接步骤见仓库 [README](../../README.md)。
