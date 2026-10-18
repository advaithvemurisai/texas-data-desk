"""Pulling one dataset into a new dated raw snapshot."""

import logging
from datetime import UTC, date, datetime
from pathlib import Path

from tdd_ingest import __version__
from tdd_ingest.http import Http
from tdd_ingest.registry import Dataset
from tdd_ingest.snapshot import CountCheck, Manifest, SnapshotWriter
from tdd_ingest.sources import SourceChangedError, build_source

log = logging.getLogger(__name__)

# Live datasets can gain a few rows between the count request and the last page.
COUNT_TOLERANCE = 0.005


class CountMismatchError(RuntimeError):
    pass


def check_count(
    written: int, expected: int | None, tolerance: float = COUNT_TOLERANCE
) -> CountCheck:
    if expected is None:
        return CountCheck(status="skipped", expected=None, written=written, diff_pct=None)
    diff = abs(written - expected) / max(expected, 1)
    if diff > tolerance:
        raise CountMismatchError(
            f"wrote {written:,} rows but the source reports {expected:,} ({diff:.2%} off; "
            f"limit {tolerance:.1%})"
        )
    return CountCheck(
        status="ok" if written == expected else "warn",
        expected=expected,
        written=written,
        diff_pct=round(diff * 100, 4),
    )


def ingest(
    ds: Dataset, *, root: Path, raw: Path, snapshot_date: date, http: Http, attempts: int = 2
) -> Manifest:
    """Pull ds into raw/<id>/<snapshot_date>/. Restarts if the portal republishes mid-pull."""
    for attempt in range(1, attempts + 1):
        with SnapshotWriter(raw, ds.id, snapshot_date) as writer:
            started = datetime.now(UTC)
            try:
                result = build_source(ds, http, root).fetch(writer)
            except SourceChangedError as exc:
                if attempt == attempts:
                    raise
                log.warning("%s: %s; restarting (attempt %d/%d)", ds.id, exc, attempt + 1, attempts)
                continue
            count_check = check_count(writer.row_count, result.expected_count)
            warnings = list(result.warnings)
            if count_check.status == "warn":
                warnings.append(
                    f"row count differs from source by {count_check.diff_pct}% "
                    f"({count_check.written:,} vs {count_check.expected:,})"
                )
            manifest = Manifest(
                dataset_id=ds.id,
                snapshot_date=snapshot_date,
                source_type=ds.source.type,
                source=ds.source.model_dump(),
                requests=result.requests,
                freshness=result.freshness,
                fetched_at_start=started,
                fetched_at_end=datetime.now(UTC),
                row_count=writer.row_count,
                count_check=count_check,
                parts=writer.parts,
                originals=writer.originals,
                warnings=warnings,
                tdd_ingest_version=__version__,
            )
            writer.finalize(manifest)
            return manifest
    raise AssertionError("unreachable")
