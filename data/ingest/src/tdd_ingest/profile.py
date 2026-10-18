"""Quick profile of a raw snapshot, for the week-1 coverage and gap checks.

Prints only; nothing is written. Dates are parsed leniently from the all-string raw
columns (ISO prefixes and M/D/YYYY), which is enough to see coverage, not to analyse.
"""

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import duckdb

from tdd_ingest.registry import Dataset

YOY_FLAG = 0.40  # PLAN.md: year-over-year swings above ±40% are breaks to explain
YOY_MIN_BASE = 50  # don't flag swings on tiny months


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _date_expr(column: str) -> str:
    c = _q(column)
    return (
        f"coalesce(try_cast(substr({c}, 1, 10) as date), "
        f"try_strptime(split_part({c}, ' ', 1), '%m/%d/%Y')::date)"
    )


@dataclass
class MonthRow:
    month: date
    rows: int
    flags: list[str]


def _add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


def profile(ds: Dataset, snapshot_dir: Path) -> str:
    con = duckdb.connect()
    glob = str(snapshot_dir / "*.parquet").replace("'", "''")
    con.execute(f"create view t as select * from read_parquet('{glob}', union_by_name = true)")
    columns = [r[0] for r in con.execute("describe t").fetchall()]
    total = con.execute("select count(*) from t").fetchone()[0]  # type: ignore[index]
    out = [f"{ds.id} · snapshot {snapshot_dir.name} · {total:,} rows · {len(columns)} columns", ""]

    present = [c for c in ds.date_fields if c in columns]
    if present:
        expr = "coalesce(" + ", ".join(_date_expr(c) for c in present) + ")"
        out += _date_section(con, ds, expr, present, snapshot_dir.name)
    else:
        out.append(f"No date column found (registry date_fields: {ds.date_fields or 'none'}).")

    out += ["", "Columns (null %, approx distinct):"]
    selects = ", ".join(f"count({_q(c)}), approx_count_distinct({_q(c)})" for c in columns)
    stats = con.execute(f"select {selects} from t").fetchone() or ()
    for i, c in enumerate(columns):
        non_null, distinct = stats[2 * i], stats[2 * i + 1]
        null_pct = 100 * (1 - non_null / total) if total else 0
        out.append(f"  {c:<45} {null_pct:6.1f}%  {distinct:>10,}")
    return "\n".join(out)


def _date_section(
    con: duckdb.DuckDBPyConnection, ds: Dataset, expr: str, present: list[str], snap: str
) -> list[str]:
    snapshot_day = date.fromisoformat(snap)
    floor = ds.coverage.start or date(2000, 1, 1)
    con.execute(f"create view d as select {expr} as d from t")
    unparsed, lo, hi = con.execute("select count(*) - count(d), min(d), max(d) from d").fetchone()  # type: ignore[misc]
    outside = con.execute(
        "select count(*) from d where d < ? or d > ?", [floor, snapshot_day]
    ).fetchone()[0]  # type: ignore[index]
    monthly = dict(
        con.execute(
            "select date_trunc('month', d)::date, count(*) from d "
            "where d between ? and ? group by 1 order by 1",
            [floor, snapshot_day],
        ).fetchall()
    )
    out = [
        f"Date: {' | '.join(present)}  ·  min {lo}  ·  max {hi}",
        f"  unparseable/blank: {unparsed:,}  ·  outside {floor} … {snapshot_day}: {outside:,}",
    ]
    if not monthly:
        return out

    yearly: dict[int, int] = {}
    rows: list[MonthRow] = []
    month = min(monthly)
    while month <= max(monthly):
        n = monthly.get(month, 0)
        yearly[month.year] = yearly.get(month.year, 0) + n
        flags = ["GAP"] if n == 0 else []
        base = monthly.get(_add_months(month, -12))
        if base and base >= YOY_MIN_BASE and abs(n / base - 1) > YOY_FLAG:
            flags.append(f"YoY {n / base - 1:+.0%}")
        rows.append(MonthRow(month, n, flags))
        month = _add_months(month, 1)

    out += ["", "By year:"]
    out += [f"  {y}  {n:>10,}" for y, n in sorted(yearly.items())]
    out += ["", "By month (GAP = no rows; YoY = swing above ±40% vs. same month last year):"]
    out += [f"  {r.month:%Y-%m}  {r.rows:>9,}  {' '.join(r.flags)}" for r in rows]
    return out
