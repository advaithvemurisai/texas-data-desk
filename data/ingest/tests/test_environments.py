from datetime import date
from pathlib import Path

import pytest
from helpers import make_dataset
from pydantic import ValidationError
from tdd_ingest.environments import (
    Snapshots,
    check_environment,
    dbt_vars,
    load_snapshots,
    snapshots_path,
)
from tdd_ingest.registry import Registry, load_registry

ROOT = Path(__file__).resolve().parents[3]
SOCRATA = {"type": "socrata", "domain": "x", "dataset_id": "abcd-1234"}


def registry(*ids: str) -> Registry:
    return Registry(datasets=[make_dataset(SOCRATA, id=i) for i in ids])


def test_repo_snapshots_pin_every_dataset_in_both_environments():
    snapshots = load_snapshots(snapshots_path(ROOT))
    ids = {d.id for d in load_registry(ROOT / "data" / "registry.yaml").datasets}
    assert set(snapshots.eval) == ids
    assert set(snapshots.live) == ids


def test_unknown_environment_key_rejected():
    with pytest.raises(ValidationError):
        Snapshots.model_validate({"eval": {}, "staging": {}})


def test_check_reports_missing_unknown_and_absent_snapshots(tmp_path: Path):
    (tmp_path / "a" / "2026-10-17").mkdir(parents=True)
    snapshots = Snapshots(
        eval={"a": date(2026, 10, 17), "b": date(2026, 10, 17), "z": date(2026, 1, 1)}
    )
    problems = check_environment(snapshots, "eval", registry("a", "b", "c"), tmp_path)
    assert problems == [
        "eval: no snapshot pinned for c",
        "eval: z is not in the registry",
        f"eval: b snapshot 2026-10-17 not found under {tmp_path}",
    ]


def test_check_passes_when_every_snapshot_exists(tmp_path: Path):
    (tmp_path / "a" / "2026-10-17").mkdir(parents=True)
    snapshots = Snapshots(live={"a": date(2026, 10, 17)})
    assert check_environment(snapshots, "live", registry("a"), tmp_path) == []


def test_dbt_vars_shape():
    snapshots = Snapshots(eval={"a": date(2026, 10, 17)})
    assert dbt_vars(snapshots, "eval") == {
        "snapshot_env": "eval",
        "snapshots": {"a": "2026-10-17"},
    }
