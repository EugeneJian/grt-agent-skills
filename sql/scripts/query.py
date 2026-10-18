#!/usr/bin/env python3
"""oa_report 只读查询脚本。

用法:
    python3 query.py @file.sql          # 从 SQL 文件读取
    python3 query.py "SELECT ..."       # 直接传 SQL
    cat q.sql | python3 query.py        # 从 stdin 读取
    ... | python3 query.py --format table

输出:
    ndjson (默认): 每行一条 JSON, 便于 jq / python 后处理
    table: 对齐文本表格, 适合直接展示

连接凭据从本脚本同目录的 .env 自动加载（不入库），也可用环境变量覆盖: OA_HOST OA_PORT OA_USER OA_PWD OA_DB
依赖: pip3 install pymssql（仅在真正连接数据库时才导入）

只读校验（第一层防线）:
    词法级解析剥离字符串/注释/带引号标识符后, 只放行单条以 SELECT/WITH
    开头的语句, 并整词拒绝写操作与过程调用关键字（SELECT ... INTO、
    WITH ... INSERT、EXEC 等变体）。字符串字面量里的 'update' 等字样
    不会被误拦。该校验不替代数据库账号自身的只读权限（最终兜底）。
"""
import json
import os
import sys
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

# 词法级整词黑名单：语句已限定以 SELECT/WITH 开头, 这里的关键字按完整
# word token 匹配, 不会被字符串、注释或 [update]/"into" 这类带引号列名误触发,
# 也不会把 OFFSET/created_at 等误认成 SET/CREATE。
DENY_KEYWORDS = frozenset("""
    alter backup begin bulk commit create dbcc delete deny drop exec execute
    go grant insert into kill merge openquery opendatasource openrowset
    reconfigure restore revoke rollback shutdown truncate update use waitfor
""".split())


def load_local_env():
    """加载 skill 目录下不入库的 .env（凭据只保存在本地，不进 Git）。"""
    if not ENV_FILE.is_file():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


def tokenize(sql):
    """把 SQL 切成 (kind, text) 词法单元, kind ∈ word / str / ident / semi。

    字符串、行/块注释、[] 与 "" 引用的标识符全部折叠为占位符（注释直接
    丢弃）, 因此关键字匹配只作用于真实的裸词法单元。运算符、括号等
    对校验无意义的字符直接跳过。T-SQL 语法: '' 与 "" 与 ]] 为转义,
    块注释可嵌套。
    """
    tokens = []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if c.isspace():
            i += 1
        elif sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j < 0 else j + 1
        elif sql.startswith("/*", i):
            depth, i = 1, i + 2
            while i < n and depth:
                if sql.startswith("/*", i):
                    depth, i = depth + 1, i + 2
                elif sql.startswith("*/", i):
                    depth, i = depth - 1, i + 2
                else:
                    i += 1
        elif c == "'":
            i += 1
            while i < n:
                if sql[i] == "'":
                    if sql.startswith("''", i):
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            tokens.append(("str", "''"))
        elif c == "[":
            i += 1
            while i < n:
                if sql.startswith("]]", i):
                    i += 2
                elif sql[i] == "]":
                    i += 1
                    break
                else:
                    i += 1
            tokens.append(("ident", "[]"))
        elif c == '"':
            i += 1
            while i < n:
                if sql[i] == '"':
                    if sql.startswith('""', i):
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            tokens.append(("ident", '""'))
        elif c == ";":
            tokens.append(("semi", ";"))
            i += 1
        elif c.isalpha() or c in "_@#$":
            j = i + 1
            while j < n and (sql[j].isalnum() or sql[j] in "_@#$"):
                j += 1
            tokens.append(("word", sql[i:j]))
            i = j
        else:
            i += 1
    return tokens


def split_statements(tokens):
    """按顶层分号切分；字符串/注释/引号标识符内的分号不算分隔符。"""
    statements, current = [], []
    for token in tokens:
        if token == ("semi", ";"):
            if current:
                statements.append(current)
            current = []
        else:
            current.append(token)
    if current:
        statements.append(current)
    return statements


def read_sql(argv):
    if argv:
        arg = argv[0]
        if arg.startswith("@"):
            with open(arg[1:], encoding="utf-8-sig") as f:
                return f.read()
        return arg
    if not sys.stdin.isatty():
        return sys.stdin.read()
    sys.exit(__doc__)


def validate(sql: str) -> None:
    statements = split_statements(tokenize(sql))
    if not statements:
        sys.exit("空 SQL")
    if len(statements) > 1:
        sys.exit(f"只允许单条查询, 检测到 {len(statements)} 条以 ; 分隔的语句")
    words = [text.lower() for kind, text in statements[0] if kind == "word"]
    if not words or words[0] not in ("select", "with"):
        sys.exit("只允许单条 SELECT / WITH 查询")
    bad = next((w for w in words if w in DENY_KEYWORDS), None)
    if bad:
        sys.exit(f"只读库, 拒绝执行包含 {bad.upper()} 的语句")


def fmt_table(rows, cols):
    def w(v):
        return str(v) if v is not None else "NULL"

    data = [[w(r[c]) for c in cols] for r in rows]
    widths = [len(str(c)) for c in cols]
    for row in data:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    line = " | ".join(str(c).ljust(widths[i]) for i, c in enumerate(cols))
    sep = "-+-".join("-" * x for x in widths)
    out = [line, sep] + [" | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) for row in data]
    return "\n".join(out)


def parse_args(argv):
    """分离 --format 选项与 SQL 参数；支持 --format X 与 --format=X 两种写法。"""
    fmt, rest = "ndjson", []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--format":
            i += 1
            if i < len(argv):
                fmt = argv[i]
        elif a.startswith("--format="):
            fmt = a.split("=", 1)[1]
        else:
            rest.append(a)
        i += 1
    return fmt, rest


def main():
    fmt, args = parse_args(sys.argv[1:])

    sql = read_sql(args)
    validate(sql)

    load_local_env()
    user = os.environ.get("OA_USER")
    pwd = os.environ.get("OA_PWD")
    if not user or not pwd:
        sys.exit(
            "缺少连接凭据: 请在本 skill 目录创建 .env（不入库），内容形如\n"
            "  OA_USER=...\n"
            "  OA_PWD=...\n"
            "或设置 OA_USER / OA_PWD 环境变量；详见 SKILL.md"
        )

    try:
        import pymssql
    except ImportError:
        sys.exit("缺少依赖 pymssql, 请先执行: pip3 install pymssql")

    try:
        conn = pymssql.connect(server=os.environ.get("OA_HOST", "10.5.5.163"),
                               port=int(os.environ.get("OA_PORT", "1433")),
                               user=user, password=pwd,
                               database=os.environ.get("OA_DB", "oa_report"),
                               timeout=60, login_timeout=15)
    except Exception as e:
        sys.exit(f"连接失败: {e}")

    try:
        cur = conn.cursor(as_dict=True)
        cur.execute(sql)
        rows = cur.fetchall()
        cols = list(rows[0].keys()) if rows else [d[0] for d in cur.description] if cur.description else []
        if fmt == "table":
            print(fmt_table(rows, cols))
            print(f"\n({len(rows)} 行)")
        else:
            for r in rows:
                def conv(v):
                    import datetime as _dt
                    import decimal as _dc
                    if isinstance(v, (_dt.date, _dt.datetime)):
                        return v.isoformat(sep=" ") if isinstance(v, _dt.datetime) else v.isoformat()
                    if isinstance(v, _dc.Decimal):
                        return float(v)
                    if isinstance(v, bytes):
                        return v.decode("utf-8", "replace")
                    return v
                print(json.dumps({k: conv(v) for k, v in r.items()}, ensure_ascii=False))
            print(f"-- {len(rows)} rows", file=sys.stderr)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
