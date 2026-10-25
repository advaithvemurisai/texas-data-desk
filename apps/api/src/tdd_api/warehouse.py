"""Read-only SQL access to the staging tables, the only data agents can touch.

Two sources, same tables:
- a dbt-built DuckDB file (local development and the model test), opened read-only;
- a folder of one Parquet file per staging table (the Vercel bundle, since Vercel's free plan
  rejects uploaded files over 100 MB), exposed as views of the same names.

Either way external access is disabled and locked (only the Parquet folder stays readable),
so SQL cannot read raw Parquet (which still holds personal columns), attach the eval warehouse
or load extensions (CLAUDE.md rules 2 and 3). On top of that, query() runs exactly one SELECT
statement, so COPY, ATTACH, SET, CREATE and friends never reach DuckDB.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb


class QueryRejectedError(ValueError):
    """The SQL was not a single read-only SELECT."""


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[tuple[Any, ...]]
    truncated: bool

    def as_text(self) -> str:
        lines = [" | ".join(self.columns)]
        lines += [" | ".join("" if v is None else str(v) for v in row) for row in self.rows]
        if self.truncated:
            lines.append(f"... (first {len(self.rows)} rows shown)")
        return "\n".join(lines)


def _lock(con: duckdb.DuckDBPyConnection) -> None:
    con.sql("set enable_external_access = false")
    con.sql("set lock_configuration = true")


def check_select_only(sql: str) -> None:
    """Raise unless sql is exactly one SELECT (incl. WITH, FROM-first, DESCRIBE, VALUES)."""
    try:
        statements = duckdb.extract_statements(sql)
    except duckdb.Error as exc:
        raise QueryRejectedError(f"could not parse SQL: {exc}") from exc
    if len(statements) != 1:
        raise QueryRejectedError(f"send exactly one statement, got {len(statements)}")
    if statements[0].type != duckdb.StatementType.SELECT:
        raise QueryRejectedError(f"only SELECT queries are allowed, got {statements[0].type.name}")


class Warehouse:
    def __init__(self, path: Path, max_rows: int = 100) -> None:
        """path: a .duckdb file, or a folder of stg_*.parquet files."""
        self.max_rows = max_rows
        if path.is_dir():
            self._con = self._from_parquet_dir(path)
        elif path.is_file():
            self._con = duckdb.connect(str(path), read_only=True)
            _lock(self._con)
        else:
            raise FileNotFoundError(f"{path} not built (dbt build, see CLAUDE.md)")

    @staticmethod
    def _from_parquet_dir(folder: Path) -> duckdb.DuckDBPyConnection:
        files = sorted(folder.glob("stg_*.parquet"))
        if not files:
            raise FileNotFoundError(f"no stg_*.parquet files in {folder}")
        con = duckdb.connect(":memory:")
        # Must be set before external access is switched off; then only this folder is readable.
        con.execute("set allowed_directories = [?]", [f"{folder.resolve()}/"])
        _lock(con)
        for f in files:
            con.sql(f"create view {f.stem} as select * from read_parquet('{f.resolve()}')")
        return con

    def close(self) -> None:
        self._con.close()

    def query(self, sql: str) -> QueryResult:
        check_select_only(sql)
        cur = self._con.cursor()  # DB-API cursor: stable across DuckDB versions, one per query
        try:
            cur.execute(sql)
            columns = [d[0] for d in cur.description or []]
            rows = cur.fetchmany(self.max_rows + 1)
        finally:
            cur.close()
        return QueryResult(columns, rows[: self.max_rows], len(rows) > self.max_rows)

    def schema_text(self) -> str:
        """Staging tables and their columns, one line per table, for the agent prompt."""
        rows = self.query(
            "select table_name, string_agg(column_name || ' ' || data_type, ', '"
            " order by ordinal_position) from information_schema.columns"
            " where table_name like 'stg_%' group by 1 order by 1"
        ).rows
        return "\n".join(f"- {table}({cols})" for table, cols in rows)

    def row_counts(self) -> dict[str, int]:
        """Rows per staging table (exact; views have no cheap size estimate)."""
        tables = self.query(
            "select table_name from information_schema.tables"
            " where table_name like 'stg_%' order by 1"
        ).rows
        return {t: self.query(f"select count(*) from {t}").rows[0][0] for (t,) in tables}
