"""tdd-ingest: pull raw snapshots, inspect them, and manage the San Antonio 311 archive."""

import json
import logging
import re
import shutil
import subprocess
import tarfile
import tempfile
from datetime import date
from pathlib import Path
from typing import Annotated

import typer

from tdd_ingest import paths
from tdd_ingest.environments import (
    Environment,
    check_environment,
    load_snapshots,
    snapshots_path,
)
from tdd_ingest.environments import dbt_vars as environment_vars
from tdd_ingest.http import Http
from tdd_ingest.ingest import ingest
from tdd_ingest.profile import profile as profile_snapshot
from tdd_ingest.registry import Registry, load_registry
from tdd_ingest.snapshot import read_manifest, snapshot_dirs

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _context() -> tuple[Path, Registry]:
    root = paths.repo_root()
    paths.load_dotenv(root)
    return root, load_registry(paths.registry_path(root))


@app.callback()
def main(verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@app.command("list")
def list_datasets() -> None:
    """List registry datasets and their newest local snapshot."""
    root, registry = _context()
    raw = paths.raw_root(root)
    for ds in registry.datasets:
        snaps = snapshot_dirs(raw, ds.id)
        latest = snaps[-1].name if snaps else "-"
        typer.echo(
            f"{ds.id:<16} {ds.city:<12} {ds.topic:<8} {ds.source.type:<8} "
            f"{ds.coverage.kind:<13} latest: {latest}"
        )


@app.command()
def run(
    dataset_ids: Annotated[list[str] | None, typer.Argument(help="Dataset ids to pull")] = None,
    all_: Annotated[bool, typer.Option("--all", help="Pull every registry dataset")] = False,
    snapshot_date: Annotated[
        str | None, typer.Option("--date", help="Snapshot date (YYYY-MM-DD); default today")
    ] = None,
) -> None:
    """Pull datasets into new dated raw snapshots. Existing snapshots are never overwritten."""
    root, registry = _context()
    if all_ == bool(dataset_ids):
        raise typer.BadParameter("give dataset ids or --all, not both or neither")
    datasets = registry.datasets if all_ else [registry.get(i) for i in dataset_ids or []]
    day = date.fromisoformat(snapshot_date) if snapshot_date else date.today()

    failures: list[str] = []
    with Http() as http:
        for ds in datasets:
            typer.echo(f"→ {ds.id}")
            try:
                m = ingest(ds, root=root, raw=paths.raw_root(root), snapshot_date=day, http=http)
            except Exception as exc:  # report and continue with the other datasets
                failures.append(ds.id)
                typer.secho(f"  FAILED: {type(exc).__name__}: {exc}", fg="red", err=True)
                continue
            check = m.count_check
            typer.echo(
                f"  {m.row_count:,} rows in {len(m.parts)} part(s); "
                f"count check {check.status} (source {check.expected})"
            )
            for w in m.warnings:
                typer.secho(f"  warning: {w}", fg="yellow")
    if failures:
        typer.secho(f"{len(failures)} failed: {', '.join(failures)}", fg="red", err=True)
        raise typer.Exit(1)


@app.command()
def profile(
    dataset_id: str,
    snapshot: Annotated[str | None, typer.Option(help="Snapshot date; default newest")] = None,
) -> None:
    """Print row counts, date coverage, monthly gaps/swings and column null rates."""
    root, registry = _context()
    ds = registry.get(dataset_id)
    snaps = snapshot_dirs(paths.raw_root(root), ds.id)
    if snapshot:
        snaps = [s for s in snaps if s.name == snapshot]
    if not snaps:
        raise typer.BadParameter(f"no snapshot found for {dataset_id} {snapshot or ''}".strip())
    typer.echo(profile_snapshot(ds, snaps[-1]))


@app.command("compare-manifests")
def compare_manifests(
    previous: Path,
    current: Path,
    max_drop: Annotated[float, typer.Option(help="Largest allowed fractional row drop")] = 0.2,
) -> None:
    """Fail if current's row count fell more than max_drop below previous's."""
    prev, cur = read_manifest(previous), read_manifest(current)
    change = cur.row_count / prev.row_count - 1 if prev.row_count else 0.0
    typer.echo(
        f"{prev.snapshot_date}: {prev.row_count:,} → {cur.snapshot_date}: {cur.row_count:,} "
        f"({change:+.1%})"
    )
    if -change > max_drop:
        typer.secho(f"row count dropped more than {max_drop:.0%}", fg="red", err=True)
        raise typer.Exit(1)


@app.command("dbt-vars")
def dbt_vars(
    env: Annotated[Environment, typer.Argument(help="Environment in data/snapshots.yaml")],
) -> None:
    """Print dbt --vars JSON pinning each dataset to the environment's snapshot."""
    root, registry = _context()
    snapshots = load_snapshots(snapshots_path(root))
    problems = check_environment(snapshots, env, registry, paths.raw_root(root))
    if problems:
        for p in problems:
            typer.secho(p, fg="red", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(environment_vars(snapshots, env)))


ARCHIVE_ASSET = re.compile(r"^(?P<id>[a-z0-9_]+)-(?P<date>\d{4}-\d{2}-\d{2})\.tar$")


@app.command("pull-archive")
def pull_archive(
    dataset_id: Annotated[str, typer.Argument()] = "sa_311",
    release: Annotated[
        str, typer.Option(help="GitHub release holding the archive")
    ] = "sa311-archive",
) -> None:
    """Download archived weekly snapshots from a GitHub release into data/raw (needs gh)."""
    root, registry = _context()
    registry.get(dataset_id)
    if shutil.which("gh") is None:
        raise typer.BadParameter("the GitHub CLI (gh) is required")
    raw = paths.raw_root(root)
    have = {p.name for p in snapshot_dirs(raw, dataset_id)}
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [
                "gh",
                "release",
                "download",
                release,
                "--pattern",
                f"{dataset_id}-*.tar",
                "--dir",
                tmp,
            ],
            check=True,
        )
        for tar_path in sorted(Path(tmp).glob("*.tar")):
            match = ARCHIVE_ASSET.match(tar_path.name)
            if not match or match["id"] != dataset_id or match["date"] in have:
                continue
            (raw / dataset_id).mkdir(parents=True, exist_ok=True)
            with tarfile.open(tar_path) as tar:
                tar.extractall(raw / dataset_id, filter="data")
            typer.echo(f"restored {dataset_id}/{match['date']}")
