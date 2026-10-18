"""Dated raw snapshots that are written once and never modified.

Layout: data/raw/<dataset_id>/<YYYY-MM-DD>/{part-*.parquet, original/*, _manifest.json}.
Everything is built in <date>.tmp/ and renamed into place only after the manifest is written,
so a crashed or interrupted pull never leaves a half-written snapshot behind.
"""

import hashlib
import shutil
import stat
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel

MANIFEST = "_manifest.json"


class SnapshotExistsError(FileExistsError):
    pass


class SchemaDriftError(RuntimeError):
    pass


class PartInfo(BaseModel):
    file: str
    rows: int
    columns: list[str]
    sha256: str | None  # None when the part had no rows and no file was written


class OriginalInfo(BaseModel):
    file: str
    bytes: int
    sha256: str
    origin: str  # URL or manual path it came from
    last_modified: str | None = None


class CountCheck(BaseModel):
    status: str  # "ok" | "warn" | "skipped"
    expected: int | None
    written: int
    diff_pct: float | None


class Manifest(BaseModel):
    dataset_id: str
    snapshot_date: date
    source_type: str
    source: dict[str, Any]
    requests: dict[str, Any]
    freshness: dict[str, Any]
    fetched_at_start: datetime
    fetched_at_end: datetime
    row_count: int
    count_check: CountCheck
    parts: list[PartInfo]
    originals: list[OriginalInfo]
    warnings: list[str]
    tdd_ingest_version: str


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot_dirs(raw: Path, dataset_id: str) -> list[Path]:
    """Finished snapshots for a dataset, oldest first."""
    base = raw / dataset_id
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if p.is_dir() and (p / MANIFEST).is_file())


def read_manifest(path: Path) -> Manifest:
    if path.is_dir():
        path = path / MANIFEST
    return Manifest.model_validate_json(path.read_text())


class SnapshotWriter:
    def __init__(self, raw: Path, dataset_id: str, snapshot_date: date) -> None:
        self.final_dir = raw / dataset_id / snapshot_date.isoformat()
        self.tmp_dir = self.final_dir.with_name(self.final_dir.name + ".tmp")
        self.parts: list[PartInfo] = []
        self.originals: list[OriginalInfo] = []
        self._finalized = False

    @property
    def row_count(self) -> int:
        return sum(p.rows for p in self.parts)

    @property
    def original_dir(self) -> Path:
        path = self.tmp_dir / "original"
        path.mkdir(exist_ok=True)
        return path

    def __enter__(self) -> "SnapshotWriter":
        if self.final_dir.exists():
            raise SnapshotExistsError(
                f"{self.final_dir} already exists; raw snapshots are never overwritten"
            )
        if self.tmp_dir.exists():  # left over from an interrupted run
            shutil.rmtree(self.tmp_dir)
        self.tmp_dir.mkdir(parents=True)
        return self

    def __exit__(self, exc_type: object, *exc: object) -> None:
        if exc_type is not None or not self._finalized:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def write_part(self, name: str, tables: Iterable[pa.Table | pa.RecordBatch]) -> PartInfo:
        """Stream tables into <name>.parquet. Every table must have the same columns."""
        path = self.tmp_dir / f"{name}.parquet"
        writer: pq.ParquetWriter | None = None
        schema: pa.Schema | None = None
        rows = 0
        try:
            for table in tables:
                if isinstance(table, pa.RecordBatch):
                    table = pa.Table.from_batches([table])
                if table.num_rows == 0:
                    continue
                if schema is None:
                    schema = table.schema
                    writer = pq.ParquetWriter(path, schema, compression="zstd")
                elif table.schema.names != schema.names:
                    added = set(table.schema.names) - set(schema.names)
                    missing = set(schema.names) - set(table.schema.names)
                    raise SchemaDriftError(
                        f"{name}: columns changed mid-pull (added {sorted(added)}, "
                        f"missing {sorted(missing)})"
                    )
                assert writer is not None
                writer.write_table(table.cast(schema))
                rows += table.num_rows
        finally:
            if writer is not None:
                writer.close()
        info = PartInfo(
            file=path.name if schema is not None else "",
            rows=rows,
            columns=list(schema.names) if schema is not None else [],
            sha256=sha256_file(path) if schema is not None else None,
        )
        self.parts.append(info)
        return info

    def add_original(self, path: Path, origin: str, last_modified: str | None = None) -> Path:
        """Record a downloaded file already in original/, or copy a manual file into it."""
        dest = self.original_dir / path.name
        if path.resolve() != dest.resolve():
            shutil.copy2(path, dest)
        self.originals.append(
            OriginalInfo(
                file=f"original/{dest.name}",
                bytes=dest.stat().st_size,
                sha256=sha256_file(dest),
                origin=origin,
                last_modified=last_modified,
            )
        )
        return dest

    def finalize(self, manifest: Manifest) -> Path:
        (self.tmp_dir / MANIFEST).write_text(manifest.model_dump_json(indent=2) + "\n")
        for f in self.tmp_dir.rglob("*"):
            if f.is_file():
                f.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        self.tmp_dir.rename(self.final_dir)
        self._finalized = True
        return self.final_dir
