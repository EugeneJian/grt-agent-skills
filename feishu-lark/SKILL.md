---
name: feishu-lark
description: 通过 lark-cli 操作用户的飞书/Lark 账号。当用户提到飞书、Lark、云文档(docx/wiki)、电子表格、多维表格(Base)、知识库、消息/群聊、邮件、日历、任务、审批、OKR、视频会议/妙记、考勤、画板、幻灯片、Markdown 文件,或给出 feishu.cn / larksuite.com / doubao.com 的 /docx/、/wiki/、/sheets/、/base/ 链接时使用本 skill。
---

# 飞书 (Lark) 操作

前提：本机已安装并登录 `lark-cli`（npm 包 `@larksuite/cli`；安装与配置步骤见仓库 [README](../README.md)）。

## 第一步:加载对应的领域 skill

lark-cli 内嵌了 28 个领域 skill(如 `lark-doc`、`lark-sheets`、`lark-base`、`lark-wiki`、`lark-im` 等)。**执行任何飞书任务前,先读取匹配的领域 skill 并遵循其指令**:

```bash
lark-cli skills list                      # 列出全部领域 skill 及路由描述
lark-cli skills read lark-doc             # 读取某个 skill 的完整 SKILL.md
```

按任务路由(常见):
- 云文档读写/图片附件 → `lark-doc`;知识空间/节点 → `lark-wiki`
- 电子表格 → `lark-sheets`;多维表格/Base → `lark-base`
- 云盘文件/上传下载/导入导出 → `lark-drive`;原生 Markdown → `lark-markdown`
- 消息/群聊 → `lark-im`;邮件 → `lark-mail`;日历 → `lark-calendar`
- 任务 → `lark-task`;审批 → `lark-approval`;会议/妙记 → `lark-meeting`
- 认证/授权问题 → `lark-shared`;未封装的原生 API → `lark-openapi-explorer`

## CLI 用法要点

- 高层任务优先用 `+shortcut`:`lark-cli <domain> +<cmd>`,如 `lark-cli calendar +agenda`
- 查看某方法参数:`lark-cli schema <service.resource.method>`
- 任意端点兜底:`lark-cli api GET /open-apis/...`
- 输出过滤用 `--jq`,`--dry-run` 预览请求
- **风险控制**:每条命令的 `--help` 标注 read | write | high-risk-write;high-risk-write 需要 `--yes` 且必须先获得用户明确确认

## 账号信息（每用户各自配置，不写入本文件）

- 应用凭证由本人运行 `lark-cli config init` 交互式配置（App ID/Secret，存放方式以 CLI 实际配置为准，如 macOS Keychain）
- 绑定用户与 Token 状态用 `lark-cli auth status` 检查；失效时运行 `lark-cli auth login` 重新授权（需用户配合）
