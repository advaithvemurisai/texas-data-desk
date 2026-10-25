"""Typed view of data/snapshots.yaml: which raw snapshot each environment reads."""

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict

from tdd_ingest.registry import Registry

Environment = Literal["eval", "live"]


class Snapshots(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    eval: dict[str, date] = {}
    live: dict[str, date] = {}

    def dates(self, env: Environment) -> dict[str, date]:
        return getattr(self, env)


def snapshots_path(root: Path) -> Path:
    return root / "data" / "snapshots.yaml"


def load_snapshots(path: Path) -> Snapshots:
    return Snapshots.model_validate(yaml.safe_load(path.read_text()) or {})


def check_environment(
    snapshots: Snapshots, env: Environment, registry: Registry, raw: Path
) -> list[str]:
    """Problems that would make dbt read the wrong or a missing snapshot; empty when fine."""
    dates = snapshots.dates(env)
    known = {d.id for d in registry.datasets}
    problems = [f"{env}: no snapshot pinned for {i}" for i in sorted(known - dates.keys())]
    problems += [f"{env}: {i} is not in the registry" for i in sorted(dates.keys() - known)]
    for dataset_id, day in sorted(dates.items()):
        if dataset_id in known and not (raw / dataset_id / day.isoformat()).is_dir():
            problems.append(f"{env}: {dataset_id} snapshot {day} not found under {raw}")
    return problems


def dbt_vars(snapshots: Snapshots, env: Environment) -> dict[str, object]:
    """The --vars dbt needs: the environment name and one snapshot date per dataset."""
    dates = snapshots.dates(env)
    return {"snapshot_env": env, "snapshots": {k: v.isoformat() for k, v in dates.items()}}
