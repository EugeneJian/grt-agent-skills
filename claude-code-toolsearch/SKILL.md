---
name: claude-code-toolsearch
description: 'Claude Code 排障常识：ToolSearch 关键词搜索搜不到核心工具（Bash/Read/Write/Edit/Agent）不代表工具被移除，须用 select: 精确加载。当遇到 "No matching deferred tools found"、怀疑工具缺失/被禁用、或准备排查 settings/managed-settings 前先读本 skill。仅适用于 Claude Code；Pi/Codex 无此机制。'
---

# Claude Code 工具发现：select: 精确加载（防误判）

**仅适用于 Claude Code**。Pi / Codex 没有延迟工具池与 ToolSearch 机制，可跳过本文件；多机同步时无需按平台删改本 skill。

## 一句话结论

核心工具（Bash、Read、Write、Edit、Agent、Grep、Glob 等）在延迟工具池中对**关键词/正则搜索不可见**——搜 `bash`、`agent`、`read`、`file` 等一律返回 `No matching deferred tools found`——但它们**并未被移除**，只能用 `select:` 按工具名精确加载：

```
ToolSearch query="select:Bash,Read,Write,Edit,Agent"
```

- `select:` 逗号分隔可批量；加载成功即工具存在，直接使用
- 关键词搜索返回空 ≠ 工具不在池中；`(?i)` 等标志同样搜不到核心工具

## 怀疑"工具缺失"时的决策树

1. **先 `select:<工具名>` 精确加载** → 成功：直接干活，排查结束
2. select 也失败，才查配置层（逐条跑并记录输出）：
   - `~/.claude/settings.json` / `settings.local.json`：`permissions.deny` / `disallowedTools`
   - `/Library/Application Support/ClaudeCode/managed-settings.json`（管理员策略，本机改不了）
   - `~/.claude.json` 内 `allowedTools` / `disallowedTools`
   - 启动参数与 shell 别名（`alias claude`）
3. 全部干净仍异常：换机器对照或重装 CLI，并考虑该版本 bug

## 误判案例（2026-10-21）

某会话仅凭关键词搜索反复确认"工具被整体移除"，推理出"配置层禁用"，对 settings / managed-settings / 启动参数排了一整轮，全部白查；次日新会话用 `select:` 一次加载全部成功。教训：**搜索机制的怪癖 ≠ 工具缺失**，下结论前必须先 select 验证。

## 附带事实（免重复排查）

- `CLAUDE_CODE_CHILD_SESSION=1` 时为 CLI 子会话，工具池偏编排型（ListAgents / SendMessage / Cron / Worktree / NotebookEdit），属正常形态
- 模型后端（如经 `ANTHROPIC_BASE_URL` 路由 GLM/智谱）与工具挂载无关，不构成工具缺失的解释
- 查环境用 `env | grep -iE 'anthropic|claude'`（输出中 TOKEN/KEY/SECRET 需掩码）
