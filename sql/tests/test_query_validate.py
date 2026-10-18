"""Regression tests: read-only validation in scripts/query.py.

Only the lexical validator is tested here; database connectivity is out of
scope (the module deliberately defers pymssql/.env loading to runtime).
"""

import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/query.py"
SPEC = importlib.util.spec_from_file_location("oa_query", SCRIPT)
QUERY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(QUERY)


class TokenizeTests(unittest.TestCase):
    def test_strings_and_comments_become_placeholders(self):
        tokens = QUERY.tokenize("SELECT 1 -- insert update\n/* drop */")
        words = [t for k, t in tokens if k == "word"]
        self.assertEqual(words, ["SELECT"])
        self.assertNotIn(("word", "insert"), tokens)

    def test_semicolon_inside_string_is_not_a_separator(self):
        tokens = QUERY.tokenize("SELECT ';' AS sep, 'a;b' FROM t")
        semis = [t for t in tokens if t == ("semi", ";")]
        self.assertEqual(semis, [])

    def test_quoted_identifiers_are_not_keywords(self):
        tokens = QUERY.tokenize('SELECT [update], "into" FROM t')
        words = [t.lower() for k, t in tokens if k == "word"]
        self.assertNotIn("update", words)
        self.assertNotIn("into", words)

    def test_nested_block_comment(self):
        tokens = QUERY.tokenize("SELECT /* a /* b */ c */ 1")
        words = [t for k, t in tokens if k == "word"]
        self.assertEqual(words, ["SELECT"])

    def test_escaped_quotes_terminate_strings_correctly(self):
        tokens = QUERY.tokenize("SELECT 'it''s fine' FROM t")
        words = [t.lower() for k, t in tokens if k == "word"]
        self.assertEqual(words, ["select", "from", "t"])

    def test_offset_is_not_the_set_keyword(self):
        tokens = QUERY.tokenize("SELECT * FROM t ORDER BY id OFFSET 10 ROWS")
        words = [t.lower() for k, t in tokens if k == "word"]
        self.assertNotIn("set", words)


class ValidateAccepts(unittest.TestCase):
    def accept(self, sql):
        QUERY.validate(sql)  # 不应抛出 SystemExit

    def test_plain_select(self):
        self.accept("SELECT 1")

    def test_select_with_trailing_semicolon(self):
        self.accept("SELECT TOP 10 * FROM sap_material ORDER BY MATNR;")

    def test_cte(self):
        self.accept("WITH t AS (SELECT 1 AS n) SELECT * FROM t")

    def test_keywords_inside_string_literal(self):
        self.accept("SELECT * FROM t WHERE note = N'please update the row'")

    def test_keywords_inside_comments(self):
        self.accept("SELECT 1 -- update delete drop\n")
        self.accept("SELECT /* insert into tmp */ 1")

    def test_quoted_column_named_like_keyword(self):
        self.accept("SELECT [update], [into], \"create\" FROM t")

    def test_offset_fetch_pagination(self):
        self.accept("SELECT * FROM t ORDER BY id OFFSET 10 ROWS FETCH NEXT 5 ROWS ONLY")

    def test_semicolon_inside_string(self):
        self.accept("SELECT ';' AS sep, 'a;b' FROM t")

    def test_columns_that_contain_keyword_prefixes(self):
        self.accept("SELECT created_at, updated_marker FROM sap_material")


class ValidateRejects(unittest.TestCase):
    def reject(self, sql, *markers):
        with self.assertRaises(SystemExit) as ctx:
            QUERY.validate(sql)
        message = str(ctx.exception)
        for marker in markers:
            self.assertIn(marker, message)

    def test_empty_sql(self):
        self.reject("   \n-- 只有注释\n", "空 SQL")

    def test_update_rejected(self):
        self.reject("UPDATE t SET x = 1", "只允许单条 SELECT / WITH")

    def test_delete_drop_truncate_rejected(self):
        for sql in ("DELETE FROM t", "DROP TABLE t", "TRUNCATE TABLE t"):
            with self.subTest(sql=sql):
                self.reject(sql, "只允许单条 SELECT / WITH")

    def test_select_into_rejected(self):
        self.reject("SELECT a, b INTO new_table FROM t", "INTO")
        self.reject("SELECT a INTO #tmp FROM t", "INTO")

    def test_cte_followed_by_insert_rejected(self):
        self.reject("WITH x AS (SELECT 1 AS n) INSERT INTO t SELECT * FROM x", "INSERT")

    def test_cte_followed_by_delete_rejected(self):
        self.reject("WITH x AS (SELECT 1 AS n) DELETE FROM t", "DELETE")

    def test_multiple_statements_rejected(self):
        self.reject("SELECT 1; SELECT 2", "单条")
        self.reject("SELECT 1; DROP TABLE t", "单条")
        self.reject("SET NOCOUNT ON; SELECT 1", "单条")

    def test_procedure_calls_rejected(self):
        self.reject("EXEC sp_help", "只允许单条 SELECT / WITH")
        self.reject("sp_executesql N'SELECT 1'", "只允许单条 SELECT / WITH")

    def test_permission_and_admin_statements_rejected(self):
        for sql in ("GRANT SELECT ON t TO u", "BACKUP DATABASE x TO DISK='y'",
                    "KILL 57", "USE other_db", "DBCC CHECKDB('x')"):
            with self.subTest(sql=sql):
                self.reject(sql, "只允许单条 SELECT / WITH")

    def test_merge_rejected(self):
        self.reject("MERGE INTO t USING s ON 1=1 WHEN MATCHED THEN UPDATE SET x=1;",
                    "只允许单条 SELECT / WITH")

    def test_adhoc_rowset_functions_rejected(self):
        self.reject("SELECT * FROM OPENROWSET('SQLNCLI', 'srv', 'q')", "OPENROWSET")
        self.reject("SELECT * FROM OPENQUERY(lnk, 'q')", "OPENQUERY")

    def test_string_keyword_does_not_block_write_detection(self):
        # 反向确认：字符串里有关键字不误拦，但真实写操作关键字仍被拦截
        self.reject("SELECT 'safe' FROM t; UPDATE t SET x = 1", "单条")


if __name__ == "__main__":
    unittest.main()
