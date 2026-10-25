from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient
from tdd_api import config, main


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    bundle = tmp_path / "warehouse"
    bundle.mkdir()
    with duckdb.connect() as con:
        con.sql(f"copy (select range as a from range(3)) to '{bundle / 'stg_x.parquet'}'")
    monkeypatch.setenv("TDD_WAREHOUSE", str(bundle))
    main.warehouse.cache_clear()
    yield TestClient(main.app)
    main.warehouse().close()
    main.warehouse.cache_clear()


def test_health_queries_the_warehouse(client: TestClient):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["tables"] == {"stg_x": 3}


def test_warehouse_path_prefers_env_then_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TDD_WAREHOUSE", str(tmp_path / "x.duckdb"))
    assert config.warehouse_path() == tmp_path / "x.duckdb"
    monkeypatch.delenv("TDD_WAREHOUSE")
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    monkeypatch.setattr(config, "BUNDLED_WAREHOUSE", bundle)
    assert config.warehouse_path().name == "warehouse_live.duckdb"  # empty bundle: checkout
    (bundle / "stg_x.parquet").touch()
    assert config.warehouse_path() == bundle


def test_vercel_entrypoint_exposes_the_app():
    import importlib.util

    spec = importlib.util.spec_from_file_location("entry", config.API_ROOT / "app.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.app is main.app
