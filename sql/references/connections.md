# 公司部署与查询通道

从 GitHub 下载 Skill 后在另一台电脑接入，见 [多机同步与登录](new-computer.md)。`scripts/setup_cloud.py` 初始化该电脑的配置和公开 Key，员工在该电脑重新登录，不同步旧机器的 access / refresh token。

## 共用 Skill 和环境配置

分发整个 `sql` 文件夹（不含 `.env`、凭据、数据）。让各 Agent 按自己的 Skill 发现机制加载 `SKILL.md`，或提供该文件绝对路径。各宿主需能执行 Python；云端无 Python 第三方依赖，内网 PostgreSQL 另装 `psql`。SQL Server 原功能依赖 `pymssql`。

将 [profiles.example.json](profiles.example.json) 配置到 `~/.config/company-sql/profiles.json`，或通过 `COMPANY_SQL_CONFIG` 指向环境配置。标准 `default_profile` 为 `intranet`，省略 `--profile` 即使用内网 SQL Server `rd_delivery` / `sap_material`；依赖 `pymssql`，详见 [内网交货](intranet-delivery.md)。profile 名称和连接元数据可以分发，密码、JWT 不随 Skill 分发。其他 Agent 主机优先配置自己的内网凭据；需要云端时另行登录。任何通道失败都报告错误，不自动回退。

本机部署另保留 `local`，用于同步验证。验证时显式传 `--profile local`，或使用 `compare_profiles.py --left local --right cloud`。`intranet` 当前指 SQL Server；下述 PostgreSQL 部署若实施，应另用 profile 名，不覆盖 SQL Server。

## 内网 PostgreSQL

IT 提供公司可达的 PostgreSQL 主机、数据库、TLS 证书和专用只读登录账号，部署相同 `shipping.report_*` 视图及 `master_data` 副本。账号授予必要 schema 的 USAGE、视图及其依赖表的 SELECT 和对应 RLS，禁止写入 / DDL。客户端额外启用 `default_transaction_read_only` 和超时，但权限由数据库账号兜底。

推荐用 libpq service 保存非敏感连接参数，例如 `~/.pg_service.conf`：

```ini
[company_shipping_ro]
host=postgres.internal.example
port=5432
dbname=shipping_analytics
user=employee_readonly
sslmode=verify-full
sslrootcert=/path/to/company-ca.pem
```

密码由 libpq `.pgpass` / `PGPASSFILE` 或受管进程环境注入，文件权限遵守客户端要求。Skill 配置里只填 `service`，也支持 `connection` 内的非敏感参数覆盖。网络连接强制 `verify-full`；已有本机 Unix socket 验证配置不启用 TLS。不能把 `postgresql://...:密码@...` 放配置中。

账号与审计建议按员工 / 应用分配；公司服务器尚未提供时，`local` 的结果仅能证明本机通道，不等于公司内网部署已完成。

## 云端 Supabase HTTPS Data API

API 与内网库使用相同数据集。HTTPS 通道无需办公网 / VPN 或 MCP；实际地区的 DNS、TLS 和连通性需要在目标网络测量。

部署方需要：

1. 在目标项目创建专用 `agent_api` schema，只放字段受控的查询视图。视图使用 `security_invoker=true`，映射见 `datasets.json`；不能给客户端任意 SQL 执行入口。
2. 将该 schema 加入 Data API 的 Exposed schemas；`shipping` / `master_data` 保持不直接暴露。仅有 schema 设置或仅有 GRANT 都不足以完成访问。
3. 接入员工身份，由公司授权机制限制读取权限。若用 Supabase Auth，授权信息放管理员维护的 `app_metadata` 或受控权限表，不能信任可由用户修改的 `user_metadata`。底层表配置对应员工 SELECT RLS，所有视图依赖也需 SELECT / schema USAGE。禁止给全体 `authenticated` 无条件放行，禁止 `anon` 读取业务数据。
4. 宿主可向 Agent 进程提供 `COMPANY_SUPABASE_URL`、`COMPANY_SUPABASE_API_KEY`（publishable 或兼容 anon Key）和 `COMPANY_SUPABASE_USER_JWT`（授权身份访问 token）。也可在 profile 设置 `credentials_file` 指向 Skill 之外的本机会话文件（0600，仅当前用户所有），保存项目 URL、公开 Key 和该身份的 access / refresh token。文件会话在到期前自动续期，采用进程锁和原子写入处理 token 轮换；不保存初始密码、不借用其他客户端 OAuth。环境变量指定的完整会话优先使用，由宿主刷新。API Key 本身不等于身份授权。

查询客户端发送 GET `/rest/v1/<resource>`，`Accept-Profile: agent_api`、`apikey`、`Authorization: Bearer <员工JWT>` 和 `Prefer: count=exact`。拒绝跨站重定向及管理员 / service_role 身份。超时默认 30 秒。当前项目已以授权员工身份完成真实 HTTPS 查询；其他项目需按公司授权方案发布 API 并实测，不能仅凭模拟测试宣称已开通。

JWT 的数据库 role 默认只接受 `authenticated`；公司若使用自定义只读 JWT role，可在 profile 配置 `allowed_jwt_roles`。JWT 真伪、有效期和数据权限由服务器验证，客户端读取 role 只用于拒绝误用身份，不能代替服务端认证。

若部署使用 `agent_access.readers` 白名单，只有列入且 enabled 的身份才可读业务数据；普通登录不自动获权。员工身份或应用身份都应分别授权，不共享管理员凭据。已有 Auth 账号可在终端运行 `scripts/auth_login.py --profile cloud --email <邮箱>`，交互输入密码并保存该身份会话；此命令不会创建账号或自动授予数据权限。

也支持 `scripts/auth_login.py --profile cloud --email <邮箱> --email-link`：向本人邮箱请求一次性登录链接，可按 Auth 项目设置自动注册该邮箱。用户在本机终端粘贴邮件中的原始登录链接（先不要点击）或验证码，内容不会回显，也不要发到聊天里。验证成功后才保存会话；业务白名单仍由管理员单独批准和维护。

若希望直接点击邮件登录，先启动 `scripts/auth_callback.py --profile cloud --email <邮箱>`，再打开 `http://127.0.0.1:3000/` 请求登录邮件，点击最新邮件里的链接。接收器仅监听本机 IPv4 / IPv6 回环，10 分钟后或保存成功后退出；会清除地址栏中的会话片段，核对已验证邮箱并交换 refresh session，再保存 0600 文件。默认对应项目已配置的 `http://localhost:3000`；其他项目先核对 Auth 的允许回调地址。点击邮件后 localhost 拒绝连接通常表示接收器尚未启动；若标签页仍保留登录片段，启动后刷新即可，必要时将主机名改为 `127.0.0.1`，无需复制令牌到聊天。不要让两个登录程序同时验证同一条一次性链接。

实际项目 URL 由部署方提供，写入该电脑的 profile；公开示例使用占位项目地址，不绑定内部部署坐标。

## 实测方法

先分别执行同一份 [九月查询](september-2026.json) 和 [1–9 月查询](january-september-2026.json)。`scripts/compare_profiles.py` 会读取两侧全部页面、比较字段 / 值 / 重复次数，并报告各侧耗时和结果摘要：

```bash
python3 <skill_dir>/scripts/compare_profiles.py --left intranet --right cloud @<skill_dir>/references/january-september-2026.json
```

使用 `--config` 指定测试配置。只有两端都成功且结果一致才是跨通道测试通过；失败会返回非零退出码。普通九月查询用 [全部产品线例子](september-2026-all-lines.json)，专项核对使用其指定产品线的样例。业务数量、行数及验收报告通过授权查询取得，不随公开 Skill 发布。

两端数据不同先核对源批次、同步时间和视图版本；不要为“对上”修改事实数据。耗时包含建连 / HTTPS / 取数，不能直接称作数据库性能比较。重复测试时保留同一查询、行数与测试网络；地区测试分别在实际网络运行并记录。

## 官方依据

- [PostgreSQL libpq service 配置](https://www.postgresql.org/docs/17/libpq-pgservice.html)
- [psql 客户端参数](https://www.postgresql.org/docs/17/app-psql.html)
- [Supabase 自定义 API schema](https://supabase.com/docs/guides/api/using-custom-schemas)
- [Supabase RLS 与视图权限](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [PostgREST 分页与精确计数](https://docs.postgrest.org/en/stable/references/api/pagination_count.html)
