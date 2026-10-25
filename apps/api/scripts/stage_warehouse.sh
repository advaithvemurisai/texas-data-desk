#!/usr/bin/env bash
# Export the live warehouse as one zstd Parquet file per staging table into
# apps/api/data/warehouse/, which `vercel deploy` (run from apps/api) bundles. Parquet, not the
# .duckdb file, because Vercel's free plan rejects uploaded files over 100 MB.
# Never the eval warehouse: gold SQL only runs there (CLAUDE.md rule 3).
set -euo pipefail
root="$(cd "$(dirname "$0")/../../.." && pwd)"
src="$root/data/warehouse_live.duckdb"
dest="$root/apps/api/data/warehouse"
[ -f "$src" ] || { echo "missing $src: build it with dbt (see CLAUDE.md)" >&2; exit 1; }
rm -rf "$dest" "$root/apps/api/data/warehouse.duckdb"
mkdir -p "$dest"
cd "$root"
uv run python - "$src" "$dest" <<'PY'
import sys
from pathlib import Path

import duckdb

src, dest = sys.argv[1], Path(sys.argv[2])
limit = 95_000_000  # Vercel Hobby rejects files over 100 MB
with duckdb.connect(src, read_only=True) as con:
    tables = [t for (t,) in con.sql("select table_name from duckdb_tables() order by 1").fetchall()]
    for t in tables:
        out = dest / f"{t}.parquet"
        con.sql(f"copy {t} to '{out}' (format parquet, compression zstd, compression_level 9)")
        size = out.stat().st_size
        print(f"{t:30s} {size / 1e6:6.1f} MB")
        if size > limit:
            sys.exit(f"{out.name} is over {limit / 1e6:.0f} MB: split it before deploying")
PY
echo "staged $(du -sh "$dest" | cut -f1) at apps/api/data/warehouse/"
