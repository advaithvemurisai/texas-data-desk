from datetime import date
from pathlib import Path

import pyarrow.parquet as pq
import pytest
import respx
from helpers import make_dataset
from tdd_ingest.http import Http
from tdd_ingest.ingest import ingest
from tdd_ingest.snapshot import sha256_file
from tdd_ingest.sources.csvfile import ManualDownloadRequiredError

DAY = date(2026, 10, 17)
URL = "https://hpd.test/xls/NIBRSPublicView{}.csv"
# HPD files start with a BOM and renamed columns between years.
CSV_2023 = "﻿Incident,RMSOccurrenceDate,OffenseCount\n2423,1/1/2023,1\n2823,1/1/2023,2\n"
CSV_2026 = "﻿Incident,Occurrence Date,Offense Count\n027174226,2026-01-01,1\n"


def dataset(manual: bool = True):
    files = [
        {
            "label": str(y),
            "url": URL.format(y),
            **({"manual_path": f"data/manual/houston/NIBRSPublicView{y}.csv"} if manual else {}),
        }
        for y in (2023, 2026)
    ]
    return make_dataset({"type": "csv", "files": files}, city="houston", topic="crime")


def test_one_part_per_file_keeping_each_files_columns(
    respx_mock: respx.MockRouter, http: Http, tmp_path: Path
):
    respx_mock.get(URL.format(2023)).respond(
        content=CSV_2023.encode(),
        headers={"content-type": "text/csv", "last-modified": "Fri, 20 Jun 2025"},
    )
    respx_mock.get(URL.format(2026)).respond(
        content=CSV_2026.encode(), headers={"content-type": "text/csv"}
    )

    m = ingest(dataset(), root=tmp_path, raw=tmp_path, snapshot_date=DAY, http=http)

    snap = tmp_path / "test_ds" / DAY.isoformat()
    t23 = pq.read_table(snap / "part-2023.parquet")
    t26 = pq.read_table(snap / "part-2026.parquet")
    assert t23.column_names == ["Incident", "RMSOccurrenceDate", "OffenseCount", "source_file"]
    assert t26.column_names == ["Incident", "Occurrence Date", "Offense Count", "source_file"]
    assert t26.column("Incident").to_pylist() == ["027174226"]  # leading zeros kept
    assert t23.column("source_file").to_pylist() == ["NIBRSPublicView2023.csv"] * 2
    assert m.row_count == 3
    original = m.originals[0]
    assert original.last_modified == "Fri, 20 Jun 2025"
    assert original.sha256 == sha256_file(snap / original.file)
    assert (snap / original.file).read_bytes() == CSV_2023.encode()


def test_html_redirect_falls_back_to_manual_file(
    respx_mock: respx.MockRouter, http: Http, tmp_path: Path
):
    respx_mock.get(URL.format(2023)).respond(
        text="<html>moved</html>", headers={"content-type": "text/html"}
    )
    respx_mock.get(URL.format(2026)).respond(
        content=CSV_2026.encode(), headers={"content-type": "text/csv"}
    )
    manual = tmp_path / "data/manual/houston/NIBRSPublicView2023.csv"
    manual.parent.mkdir(parents=True)
    manual.write_text(CSV_2023)

    m = ingest(dataset(), root=tmp_path, raw=tmp_path / "raw", snapshot_date=DAY, http=http)

    assert m.row_count == 3
    assert m.originals[0].origin == "data/manual/houston/NIBRSPublicView2023.csv"
    assert any("used data/manual/houston" in w for w in m.warnings)
    leftovers = list((tmp_path / "raw/test_ds" / DAY.isoformat() / "original").glob("*.part"))
    assert leftovers == []


def test_missing_file_explains_manual_download(
    respx_mock: respx.MockRouter, http: Http, tmp_path: Path
):
    respx_mock.get(URL.format(2023)).respond(404)
    with pytest.raises(ManualDownloadRequiredError, match="save it as data/manual/houston"):
        ingest(dataset(), root=tmp_path, raw=tmp_path, snapshot_date=DAY, http=http)
    assert not (tmp_path / "test_ds" / DAY.isoformat()).exists()
