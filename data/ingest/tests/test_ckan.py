from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pyarrow.parquet as pq
import pytest
import respx
from helpers import make_dataset
from tdd_ingest.http import Http
from tdd_ingest.ingest import ingest
from tdd_ingest.sources.ckan import ResourceNotFoundError

API = "https://ckan.test/api/3/action"
DAY = date(2026, 10, 17)
RECORDS = [{"_id": i, "CASEID": f"C{i}", "OPENED": f"2026-0{i}-01", "DIST": i} for i in (1, 2, 3)]


def dataset(**source: Any):
    return make_dataset(
        {
            "type": "ckan",
            "base_url": "https://ckan.test",
            "package": "service-calls",
            "resource_name": "ALL SERVICE CALLS",
            "page_size": 2,
        }
        | source
    )


def package(datastore: bool = True, name: str = "ALL SERVICE CALLS") -> dict[str, Any]:
    return {
        "success": True,
        "result": {
            "metadata_modified": "2026-10-11T04:01:32",
            "license_id": "cc-by",
            "resources": [
                {"id": "dict-1", "name": "Data Dictionary", "datastore_active": False},
                {
                    "id": "res-1",
                    "name": name,
                    "datastore_active": datastore,
                    "last_modified": "2026-10-11T04:01:32",
                    "url": "https://ckan.test/download/allservicecalls.csv",
                },
            ],
        },
    }


def serve_datastore(request: httpx.Request) -> httpx.Response:
    params = request.url.params
    limit = int(params["limit"])
    if limit == 0:
        fields = [{"id": k, "type": "text"} for k in RECORDS[0]]
        return httpx.Response(200, json={"success": True, "result": {"total": 3, "fields": fields}})
    assert params["sort"] == "_id"
    offset = int(params["offset"])
    return httpx.Response(
        200, json={"success": True, "result": {"records": RECORDS[offset : offset + limit]}}
    )


def test_datastore_paging(respx_mock: respx.MockRouter, http: Http, tmp_path: Path):
    respx_mock.get(f"{API}/package_show").respond(json=package())
    search = respx_mock.get(f"{API}/datastore_search").mock(side_effect=serve_datastore)

    m = ingest(dataset(), root=tmp_path, raw=tmp_path, snapshot_date=DAY, http=http)

    assert search.call_count == 3  # head (limit=0), offset 0, offset 2
    table = pq.read_table(tmp_path / "test_ds" / DAY.isoformat() / "part-00000.parquet")
    assert table.column_names == ["CASEID", "OPENED", "DIST"]  # _id dropped
    assert table.column("DIST").to_pylist() == ["1", "2", "3"]  # stored as text
    assert m.count_check.status == "ok"
    assert m.requests["resource_id"] == "res-1"


def test_pinned_resource_renamed_fails(respx_mock: respx.MockRouter, http: Http, tmp_path: Path):
    respx_mock.get(f"{API}/package_show").respond(json=package(name="SERVICE CALLS 2027"))
    with pytest.raises(ResourceNotFoundError, match="now named"):
        ingest(
            dataset(resource_id="res-1"), root=tmp_path, raw=tmp_path, snapshot_date=DAY, http=http
        )


def test_unknown_resource_name_lists_choices(
    respx_mock: respx.MockRouter, http: Http, tmp_path: Path
):
    respx_mock.get(f"{API}/package_show").respond(json=package(name="Something else"))
    with pytest.raises(ResourceNotFoundError, match="Data Dictionary"):
        ingest(dataset(), root=tmp_path, raw=tmp_path, snapshot_date=DAY, http=http)


def test_falls_back_to_file_download(respx_mock: respx.MockRouter, http: Http, tmp_path: Path):
    respx_mock.get(f"{API}/package_show").respond(json=package(datastore=False))
    respx_mock.get("https://ckan.test/download/allservicecalls.csv").respond(
        text="CASEID,OPENED\nC1,2026-01-01\nC2,2026-02-01\n", headers={"content-type": "text/csv"}
    )
    m = ingest(dataset(), root=tmp_path, raw=tmp_path, snapshot_date=DAY, http=http)
    assert m.row_count == 2
    assert m.count_check.status == "skipped"
    assert [o.file for o in m.originals] == ["original/allservicecalls.csv"]
