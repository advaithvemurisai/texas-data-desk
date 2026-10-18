"""Plain file downloads (Houston's yearly NIBRS CSVs).

Each file becomes its own Parquet part with its own columns, because HPD renames headers
and changes date formats between years. Originals are kept byte-for-byte. When a download
is blocked or redirected to an HTML page, the registry's manual_path is used instead.
"""

from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import httpx

from tdd_ingest.http import Http
from tdd_ingest.registry import CsvFile
from tdd_ingest.registry import CsvSource as CsvConfig
from tdd_ingest.snapshot import SnapshotWriter
from tdd_ingest.sources.base import SourceResult
from tdd_ingest.tables import iter_csv_file


class ManualDownloadRequiredError(RuntimeError):
    pass


class _NotADataFileError(Exception):
    pass


class CsvFileSource:
    def __init__(self, cfg: CsvConfig, http: Http, root: Path) -> None:
        self.cfg = cfg
        self.http = http
        self.root = root

    def _obtain(self, f: CsvFile, writer: SnapshotWriter, warnings: list[str]) -> Path:
        failure = "no url configured"
        if f.url:
            name = PurePosixPath(urlparse(f.url).path).name or f"{f.label}.csv"
            dest = writer.original_dir / name
            try:
                response = self.http.download(f.url, dest)
                if "html" in response.headers.get("content-type", "").lower():
                    dest.unlink()
                    raise _NotADataFileError(f"got an HTML page from {response.url}")
                return writer.add_original(
                    dest,
                    origin=str(response.url),
                    last_modified=response.headers.get("last-modified"),
                )
            except (httpx.HTTPError, _NotADataFileError) as exc:
                failure = str(exc)
        if f.manual_path and (manual := self.root / f.manual_path).is_file():
            if f.url:
                warnings.append(f"{f.label}: download failed ({failure}); used {f.manual_path}")
            return writer.add_original(manual, origin=f.manual_path)
        raise ManualDownloadRequiredError(
            f"{f.label}: could not download ({failure}). Download it by hand"
            + (f" from {f.url}" if f.url else "")
            + (f" and save it as {f.manual_path}" if f.manual_path else "")
            + ", then rerun."
        )

    def fetch(self, writer: SnapshotWriter) -> SourceResult:
        warnings: list[str] = []
        for f in self.cfg.files:
            path = self._obtain(f, writer, warnings)
            writer.write_part(
                f"part-{f.label}",
                iter_csv_file(path, self.cfg.encoding, extra={"source_file": path.name}),
            )
        return SourceResult(
            expected_count=None,
            freshness={o.file: o.last_modified for o in writer.originals},
            requests={"files": [f.model_dump(exclude_none=True) for f in self.cfg.files]},
            warnings=warnings,
        )
