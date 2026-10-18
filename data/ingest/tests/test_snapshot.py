import os
from datetime import UTC, date, datetime
from pathlib import Path

import pyarrow as pa
import pytest
from tdd_ingest.ingest import CountMismatchError, check_count
from tdd_ingest.snapshot import (
    Manifest,
    SchemaDriftError,
    SnapshotExistsError,
    SnapshotWriter,
    read_manifest,
    sha256_file,
)

DAY = date(2026, 10, 17)


def manifest(w: SnapshotWriter) -> Manifest:
    now = datetime.now(UTC)
    return Manifest(
        dataset_id="ds",
        snapshot_date=DAY,
        source_type="socrata",
        source={},
        requests={},
        freshness={},
        fetched_at_start=now,
        fetched_at_end=now,
        row_count=w.row_count,
        count_check=check_count(w.row_count, None),
        parts=w.parts,
        originals=w.originals,
        warnings=[],
        tdd_ingest_version="test",
    )


def write_snapshot(raw: Path) -> Path:
    with SnapshotWriter(raw, "ds", DAY) as w:
        w.write_part("part-00000", [pa.table({"a": ["1", "2"]}), pa.table({"a": ["3"]})])
        return w.finalize(manifest(w))


def test_finalize_moves_tmp_into_place_read_only(tmp_path: Path):
    snap = write_snapshot(tmp_path)
    m = read_manifest(snap)
    assert snap == tmp_path / "ds" / "2026-10-17"
    assert not (tmp_path / "ds" / "2026-10-17.tmp").exists()
    assert m.row_count == 3
    assert m.parts[0].sha256 == sha256_file(snap / "part-00000.parquet")
    assert not os.access(snap / "part-00000.parquet", os.W_OK)


def test_refuses_to_overwrite_existing_snapshot(tmp_path: Path):
    write_snapshot(tmp_path)
    with pytest.raises(SnapshotExistsError):
        write_snapshot(tmp_path)


def test_nothing_is_visible_after_a_failed_pull(tmp_path: Path):
    def pages():
        yield pa.table({"a": ["1"]})
        raise ConnectionError("portal went away")

    with pytest.raises(ConnectionError), SnapshotWriter(tmp_path, "ds", DAY) as w:
        w.write_part("part-00000", pages())
    assert list((tmp_path / "ds").iterdir()) == []


def test_stale_tmp_from_a_killed_run_is_replaced(tmp_path: Path):
    stale = tmp_path / "ds" / "2026-10-17.tmp"
    stale.mkdir(parents=True)
    (stale / "junk.parquet").write_text("x")
    snap = write_snapshot(tmp_path)
    assert not (snap / "junk.parquet").exists()


def test_column_drift_mid_pull_raises(tmp_path: Path):
    with (
        pytest.raises(SchemaDriftError, match="added \\['b'\\]"),
        SnapshotWriter(tmp_path, "ds", DAY) as w,
    ):
        w.write_part("part-00000", [pa.table({"a": ["1"]}), pa.table({"a": ["2"], "b": ["x"]})])


@pytest.mark.parametrize(
    ("written", "expected", "status"),
    [(100, 100, "ok"), (1000, 1004, "warn"), (5, None, "skipped")],
)
def test_count_check(written: int, expected: int | None, status: str):
    assert check_count(written, expected).status == status


def test_count_check_fails_beyond_tolerance():
    with pytest.raises(CountMismatchError):
        check_count(900, 1000)
