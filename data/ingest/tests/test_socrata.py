from datetime import date
from pathlib import Path

import httpx
import pyarrow.parquet as pq
import pytest
import respx
from helpers import csv_text, make_dataset
from tdd_ingest.http import Http
from tdd_ingest.ingest import ingest
from tdd_ingest.snapshot import read_manifest
from tdd_ingest.sources import SourceChangedError

BASE = "https://portal.test"
HEADER = [":id", ":created_at", ":updated_at", ":version", "sr", "created"]
ROWS = [[f"row-{i}", "t", "t", "v", f"SR{i}", f"2024-0{i}-01T00:00:00.000"] for i in range(1, 6)]
DAY = date(2026, 10, 17)


def dataset(page_size: int = 2):
    return make_dataset(
        {
            "type": "socrata",
            "domain": "portal.test",
            "dataset_id": "abcd-1234",
            "page_size": page_size,
        }
    )


def serve_pages(request: httpx.Request) -> httpx.Response:
    """Fake keyset paging over ROWS using $where=:id > 'row-N'."""
    params = request.url.params
    assert params["$order"] == ":id"
    assert params["$select"] == ":*,*"
    limit = int(params["$limit"])
    start = 0
    if where := params.get("$where"):
        last = where.split("'")[1]
        start = [r[0] for r in ROWS].index(last) + 1
    page = ROWS[start : start + limit]
    return httpx.Response(200, text=csv_text(HEADER, page) if page else "")


def mock_portal(mock: respx.MockRouter, updated_at: list[int] | None = None) -> respx.Route:
    stamps = iter(updated_at or [1] * 10)
    mock.get(f"{BASE}/api/views/abcd-1234.json").mock(
        side_effect=lambda _: httpx.Response(200, json={"rowsUpdatedAt": next(stamps)})
    )
    mock.get(f"{BASE}/resource/abcd-1234.json").respond(json=[{"count": str(len(ROWS))}])
    return mock.get(f"{BASE}/resource/abcd-1234.csv").mock(side_effect=serve_pages)


def test_keyset_paging_reads_every_row_once(
    respx_mock: respx.MockRouter, http: Http, tmp_path: Path
):
    pages = mock_portal(respx_mock)
    m = ingest(dataset(), root=tmp_path, raw=tmp_path, snapshot_date=DAY, http=http)

    # 2 + 2 + 1 rows; the short third page ends the pull without an extra request.
    assert pages.call_count == 3
    assert pages.calls[1].request.url.params["$where"] == ":id > 'row-2'"
    table = pq.read_table(tmp_path / "test_ds" / DAY.isoformat() / "part-00000.parquet")
    assert table.column(":id").to_pylist() == [r[0] for r in ROWS]
    assert all(str(f.type) == "string" for f in table.schema)
    assert m.row_count == 5
    assert m.count_check.status == "ok"
    assert m.freshness["rowsUpdatedAt"] == 1


def test_stops_on_empty_page(respx_mock: respx.MockRouter, http: Http, tmp_path: Path):
    pages = mock_portal(respx_mock)
    m = ingest(dataset(page_size=5), root=tmp_path, raw=tmp_path, snapshot_date=DAY, http=http)
    assert pages.call_count == 2  # a full page, then an empty one
    assert m.row_count == 5


def test_app_token_header(
    respx_mock: respx.MockRouter, http: Http, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("SOCRATA_APP_TOKEN", "tok123")
    pages = mock_portal(respx_mock)
    ingest(dataset(), root=tmp_path, raw=tmp_path, snapshot_date=DAY, http=http)
    assert all(c.request.headers["X-App-Token"] == "tok123" for c in pages.calls)


def test_retries_429_honoring_retry_after(
    respx_mock: respx.MockRouter, http: Http, tmp_path: Path, sleeps: list[float]
):
    mock_portal(respx_mock)
    respx_mock.get(f"{BASE}/resource/abcd-1234.json").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(200, json=[{"count": "5"}]),
        ]
    )
    ingest(dataset(), root=tmp_path, raw=tmp_path, snapshot_date=DAY, http=http)
    assert sleeps == [7.0]


def test_restarts_when_dataset_is_refreshed_mid_pull(
    respx_mock: respx.MockRouter, http: Http, tmp_path: Path
):
    # before/after differ on attempt 1 (1 -> 2), match on attempt 2 (2 -> 2).
    mock_portal(respx_mock, updated_at=[1, 2, 2, 2])
    ingest(dataset(), root=tmp_path, raw=tmp_path, snapshot_date=DAY, http=http)
    snap = tmp_path / "test_ds" / DAY.isoformat()
    assert read_manifest(snap).freshness["rowsUpdatedAt"] == 2
    assert not snap.with_name(snap.name + ".tmp").exists()


def test_gives_up_if_dataset_keeps_changing(
    respx_mock: respx.MockRouter, http: Http, tmp_path: Path
):
    mock_portal(respx_mock, updated_at=[1, 2, 3, 4])
    with pytest.raises(SourceChangedError):
        ingest(dataset(), root=tmp_path, raw=tmp_path, snapshot_date=DAY, http=http)
    assert not (tmp_path / "test_ds" / DAY.isoformat()).exists()
