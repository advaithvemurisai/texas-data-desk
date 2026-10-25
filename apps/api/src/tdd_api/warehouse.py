"""Read-only SQL access to a built dbt warehouse, the only data agents can touch.

The connection is read-only and has external access disabled and locked, so SQL cannot read
raw Parquet (which still holds personal columns), attach the eval warehouse, write files or
load extensions (CLAUDE.md rules 2 and 3).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb


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


class Warehouse:
    def __init__(self, path: Path, max_rows: int = 100) -> None:
        if not path.is_file():
            raise FileNotFoundError(f"{path} not built (dbt build, see CLAUDE.md)")
        self.max_rows = max_rows
        self._con = duckdb.connect(
            str(path),
            read_only=True,
            config={"enable_external_access": False, "lock_configuration": True},
        )

    def close(self) -> None:
        self._con.close()

    def query(self, sql: str) -> QueryResult:
        rel = self._con.sql(sql)
        if rel is None:  # a statement with no result set
            return QueryResult([], [], False)
        rows = rel.fetchmany(self.max_rows + 1)
        return QueryResult(rel.columns, rows[: self.max_rows], len(rows) > self.max_rows)

    def schema_text(self) -> str:
        """Staging tables and their columns, one line per table, for the agent prompt."""
        rows = self._con.sql(
            "select table_name, string_agg(column_name || ' ' || data_type, ', '"
            " order by ordinal_position) from information_schema.columns"
            " where table_name like 'stg_%' group by 1 order by 1"
        ).fetchall()
        return "\n".join(f"- {table}({cols})" for table, cols in rows)
