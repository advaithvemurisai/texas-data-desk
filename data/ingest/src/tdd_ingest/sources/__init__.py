import os
from pathlib import Path

from tdd_ingest.http import Http
from tdd_ingest.registry import CkanSource as CkanConfig
from tdd_ingest.registry import CsvSource as CsvConfig
from tdd_ingest.registry import Dataset
from tdd_ingest.registry import SocrataSource as SocrataConfig
from tdd_ingest.sources.base import Source, SourceChangedError, SourceResult
from tdd_ingest.sources.ckan import CkanSource
from tdd_ingest.sources.csvfile import CsvFileSource
from tdd_ingest.sources.socrata import SocrataSource

__all__ = ["Source", "SourceChangedError", "SourceResult", "build_source"]


def build_source(ds: Dataset, http: Http, root: Path) -> Source:
    cfg = ds.source
    match cfg:
        case SocrataConfig():
            return SocrataSource(cfg, http, os.environ.get("SOCRATA_APP_TOKEN") or None)
        case CkanConfig():
            return CkanSource(cfg, http)
        case CsvConfig():
            return CsvFileSource(cfg, http, root)
