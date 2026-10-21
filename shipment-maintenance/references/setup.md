# 配置与权限

出货权威目标已指定为 `oa_report.dbo.rd_delivery`，物料权威源仍为 `sap_material`。当前结构升级与历史验收尚未完成，保持 `report_only`。PostgreSQL 历史仅作一次性迁移输入；切换后本机与 Supabase 均由内网已提交版本发布。 配置以 `shipment_ssot="oa_report.dbo.rd_delivery"` 和 `ssot_cutover_status="pending_schema_upgrade"` 记录状态；结构升级由 DBA 配合完成。旧的本机→云端直写模式不用于新权威入库。

默认使用内网差异模式：配置 `target="intranet"`、`mode="report_only"`、`intranet_profile="intranet"`，查询配置指向 SQL Skill 的 `mssql_rd_delivery` profile。`doctor` 只读探测现有表，`delivery_diff.py --from-month YYYY-MM-01 --through-month YYYY-MM-01` 比较本机 PCS 月度汇总与旧表原值，结果存私有批次目录，不发云端、不修改数据库和归档。内网驱动需要 `pymssql`；可使用已安装它的宿主 Python。内网写入适配尚未启用。

下面的云端部署仅适用于另行批准并显式配置 `target="cloud"` 的环境；云端权限不足时不自动部署角色 / RLS / RPC。

Skill 与同仓库 `sql` 一起安装到宿主共享 Skill 目录，供各 Agent 使用；连接配置、批次、Excel、业务报告和会话都留在仓库外。安装依赖到独立虚拟环境：`python3 -m pip install -r <skill_dir>/requirements.txt`。

将 [配置示例](maintenance.example.json) 复制到 `~/.config/company-sql/maintenance.json`，替换工作区和本机维护连接。`sql_skill` 指向已安装的只读 SQL Skill；`query_config` 指向它的连接配置，`cloud_profile` 选已有 Supabase HTTPS profile。它复用该电脑本人重新登录的员工会话，不复制其他电脑的 token。

工作区需有 `Excel资料/00_新增待处理`、`02_导入批次`、`04_台账/文件台账.json`。新工作区先由管理员核对历史文件与数据库完成状态，建立含 `files` 数组的台账；不能把未验证的目录直接标成已入库。归档原件在 `01_已入库归档`，单批次来源 ZIP 和数据库备份存 `02_导入批次`。台账支持初始历史 ZIP 及逐批次 ZIP。

本机连接使用 libpq service 或非敏感 connection 字段；密码由受限 `.pgpass` 或宿主密钥环境提供，不放 Skill 或 JSON。网络 PostgreSQL 必须 `sslmode=verify-full`；Unix socket 验证库可使用已有本机配置。需 `psql`、`pg_dump`、`pg_restore`，工具大版本与数据库匹配。维护配置与日常只读 profile 分开。

## 管理员一次性部署

1. 在本机验证库安装 `sql/core.sql`；它增加私有维护函数和审计表，不改既有业务视图或历史数据。
2. 在 Supabase 应用同一 `core.sql`，再应用 `sql/cloud_api.sql`。云端 API 使用已有暴露的 `agent_api` schema，新增 `shipment_maintenance_status()` 和 `shipment_append(jsonb)` 两个 RPC；私有实现不暴露为表接口。
3. 管理员核对员工已验证的 `auth.users` 身份和既有 `agent_access.readers` 授权后，将该身份加入 `agent_access.shipment_importers`。不要因普通员工登录而自动授予维护权限。撤销 enabled 会在下一次请求阻止维护。
4. 执行 `doctor`，确认真实员工 HTTPS 可达且本机/云端基线一致。匿名、未获维护授权的员工必须失败；普通 authenticated 身份仍不得直接 INSERT/UPDATE/DELETE 业务表。

`shipping_import_executor` 是 NOLOGIN、NOBYPASSRLS 的内部执行角色，不授予员工角色成员关系。固定入口先检查员工双重白名单，再调用受限导入函数；执行角色只具备所需表权限，没有业务明细 UPDATE/DELETE 或任意 SQL 入口。只有部署管理员能修改函数。

数据库 SQL 是管理员安装资源，运行维护命令不会自行执行 DDL。尚未配置维护权限时明确报告未接通，不把模拟测试称作部署成功。已有同名对象/政策先核对版本，不能盲目重建或重复执行首次安装。

依据：[Supabase 数据库函数与执行权限](https://supabase.com/docs/guides/database/functions)、[RLS](https://supabase.com/docs/guides/database/postgres/row-level-security)、[PostgreSQL 事务级 advisory lock](https://www.postgresql.org/docs/17/explicit-locking.html#ADVISORY-LOCKS)。
