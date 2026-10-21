> 默认入口已改为内网 SQL Server：先安装 `pymssql`，在本机安全配置 OA 连接，按 `profiles.example.json` 使用 `intranet`。以下步骤用于显式启用可选 `cloud`；不要覆盖已经配置的内网默认入口。参见 [内网交货](intranet-delivery.md)。

# 从 GitHub 同步 Skill，并在新电脑登录

GitHub 分发 Skill 文件；每台电脑的连接配置与员工会话保存在仓库之外。已有账号在新电脑用同一员工邮箱重新登录，沿用服务器现有的只读授权。其他员工仍需管理员单独加入业务白名单。

## 获取 Skill

仓库为 `https://github.com/EugeneJian/grt-agent-skills`。使用包含 `scripts/setup_cloud.py` 的最新版。

新环境可克隆到 `~/.agents/skills`，目标已有内容时先盘点，不要覆盖。也可用 GitHub 的 **Code → Download ZIP**，解压后将 `sql` 完整目录安放到 `~/.agents/skills/sql`。已有仓库先检查 `git status --short`，工作区干净时才运行 `git pull --ff-only`；Download ZIP 安装后续需比较并更新 Skill 文件。

Pi 可直接扫描 `~/.agents/skills`，更新后 `/reload`。Claude Code、Codex 的共享目录链接沿用仓库根目录部署说明；其他 Agent 配置读取同一个 `sql/SKILL.md`。不要为同步 Skill 复制整个用户配置目录。

## 初始化云端连接

仅需 Python 3.9+，HTTPS 查询不需要 PostgreSQL、pymssql 或 Supabase MCP。下列命令从仓库根目录运行；Windows 使用 `python` 或 `py -3` 替换 `python3`。

```bash
python3 sql/scripts/setup_cloud.py --url https://your-project.supabase.co
```

将示例 URL 替换为部署方提供的实际项目 URL；它保存在该电脑的配置中，GitHub 不分发实际部署坐标。

首次运行时在终端粘贴项目的 **Publishable key**（或兼容 anon key），不回显；可从 Supabase 项目 Settings → API Keys 获取。宿主也可通过 `COMPANY_SUPABASE_API_KEY` 注入。它是项目客户端标识，本身不授予业务读取权限。不要填 secret key、service_role 或员工 JWT。

脚本在 `~/.config/company-sql/` 创建配置及仅含项目 URL、公开 Key 的初始会话文件，已有默认入口保持不变；仅云端初始化的空配置默认 `cloud`，内网部署须按示例配置 `intranet`。已有同项目会话不改写，保留其他 profile；已有不同项目的 cloud 配置则停止。可用 `--config` 和 `--session-file` 指定独立路径。

## 本人登录

```bash
python3 sql/scripts/auth_callback.py --profile cloud --email <本人员工邮箱>
```

保持终端运行，打开 `http://127.0.0.1:3000/`，发送新登录邮件并点击最新邮件的链接。看到“登录已安全保存”后，再执行查询。使用自定义配置时，登录和查询均传同一个 `--config`。localhost 拒绝连接时先确认接收器已启动；不要复制地址栏令牌到聊天或 GitHub。

登录后，该电脑单独保存并自动续期员工会话。**不要将旧电脑的 `cloud-auth.json` 复制到新电脑**：两台电脑独立登录，避免共用轮换中的 refresh token。会话保存在用户配置目录，POSIX 文件权限为 0600；Windows 应保留用户目录的专属 ACL，不放到多人共享目录。

## 查询验证与后续更新

```bash
python3 sql/scripts/query_data.py @sql/references/september-2026-all-lines.json
```

返回应显示 `profile: cloud`。该例查询 2026 年 9 月全部产品线，默认不含机壳，按单位返回数量；统计口径见 [出货口径](shipping-analysis.md)。业务数量通过授权查询取得，连接失败不能当成零出货。

以后更新 GitHub Skill 通常无需重新登录，配置与会话仍在仓库外。会话失效或被撤销时，在该电脑重新登录。本机 PostgreSQL 仅在原电脑保留用于同步验证，不需要随 Skill 复制数据库。

不提交 `.env`、`cloud-auth.json`、密码、access/refresh token、登录邮件或数据库备份。GitHub 登录权限与 Supabase 业务读取权限各自独立。

依据：[Supabase 会话与 refresh token 轮换](https://supabase.com/docs/guides/auth/sessions)、[项目 API Keys](https://supabase.com/docs/guides/api/api-keys)。
