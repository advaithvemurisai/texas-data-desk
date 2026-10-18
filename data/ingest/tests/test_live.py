"""Smoke tests against the real portals. Run with `uv run pytest -m live`; never in CI."""

import pytest
from tdd_ingest.http import Http
from tdd_ingest.paths import registry_path, repo_root
from tdd_ingest.registry import CkanSource as CkanConfig
from tdd_ingest.registry import CsvSource as CsvConfig
from tdd_ingest.registry import SocrataSource as SocrataConfig
from tdd_ingest.registry import load_registry
from tdd_ingest.sources.ckan import CkanSource
from tdd_ingest.sources.socrata import SocrataSource

pytestmark = pytest.mark.live
REGISTRY = load_registry(registry_path(repo_root()))


@pytest.fixture(scope="module")
def http():
    with Http() as client:
        yield client


@pytest.mark.parametrize("ds", REGISTRY.datasets, ids=lambda d: d.id)
def test_source_reachable(ds, http: Http):
    cfg = ds.source
    if isinstance(cfg, SocrataConfig):
        source = SocrataSource(cfg.model_copy(update={"page_size": 5}), http)
        assert source.count() > 0
        page = next(source.pages())
        assert page.num_rows == 5
        assert set(ds.date_fields) & set(page.column_names)
    elif isinstance(cfg, CkanConfig):
        source = CkanSource(cfg, http)
        _, resource = source.resource()
        assert resource["datastore_active"]
        head = source._action("datastore_search", resource_id=resource["id"], limit="1")
        assert head["total"] > 0
        assert set(ds.date_fields) & {f["id"] for f in head["fields"]}
    elif isinstance(cfg, CsvConfig):
        for f in cfg.files:
            assert f.url
            r = http.client.get(f.url, headers={"Range": "bytes=0-0"})
            assert r.status_code in (200, 206), f"{f.label}: HTTP {r.status_code}"
            assert "html" not in r.headers.get("content-type", "")
