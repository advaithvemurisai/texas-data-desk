"""CLAUDE.md rule 2: dbt staging never exposes a registry pii_column."""

import re
from pathlib import Path

import duckdb
import pytest
from tdd_ingest.registry import load_registry

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / "data" / "dbt" / "models" / "staging"
REGISTRY = load_registry(ROOT / "data" / "registry.yaml")
COMMENT = re.compile(r"--[^\n]*|\{#.*?#\}", re.DOTALL)


def pii_by_model() -> dict[Path, list[str]]:
    return {STAGING / f"stg_{ds.id}.sql": ds.pii_columns for ds in REGISTRY.datasets} | {
        # Dallas police is staged at offense grain under its own name.
        STAGING / "stg_dallas_police_offenses.sql": REGISTRY.get("dallas_police").pii_columns
    }


def test_every_dataset_has_a_staging_model() -> None:
    models = {p.stem for p in STAGING.glob("stg_*.sql")}
    for ds in REGISTRY.datasets:
        assert f"stg_{ds.id}" in models or any(m.startswith(f"stg_{ds.id}_") for m in models)


def test_staging_sql_never_names_a_pii_column() -> None:
    offenders = []
    for path, pii in pii_by_model().items():
        if not path.exists():
            continue
        sql = COMMENT.sub("", path.read_text())
        for col in pii:
            if re.search(rf"(?<![\w]){re.escape(col)}(?![\w])", sql, re.IGNORECASE):
                offenders.append(f"{path.name}: {col}")
    assert not offenders, f"staging SQL references personal columns: {offenders}"


@pytest.mark.parametrize("env", ["eval", "live"])
def test_built_warehouse_has_no_pii_columns(env: str) -> None:
    db = ROOT / "data" / f"warehouse_{env}.duckdb"
    if not db.exists():
        pytest.skip(f"{db.name} not built")
    pii = {c.lower() for ds in REGISTRY.datasets for c in ds.pii_columns}
    with duckdb.connect(str(db), read_only=True) as con:
        cols = con.sql(
            "select table_name, column_name from information_schema.columns "
            "where table_name like 'stg_%'"
        ).fetchall()
    leaked = [f"{t}.{c}" for t, c in cols if c.lower() in pii]
    assert not leaked, f"staging tables expose personal columns: {leaked}"
