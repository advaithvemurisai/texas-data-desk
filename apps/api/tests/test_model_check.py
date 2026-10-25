from pathlib import Path

import duckdb
import httpx
import pytest
from tdd_api.llm import ChatClient, ModelRef, QuotaExhaustedError
from tdd_api.model_check.cli import load_questions, score
from tdd_api.warehouse import QueryRejectedError, Warehouse

ANSWERED = {"status": "answered", "values": {"2024": 14122}}


def test_score_exact_values_and_key_normalisation():
    assert score(ANSWERED, {"status": "answered", "values": {"2024": 14122}, "notes": ""})[
        "correct"
    ]
    expected = {"status": "answered", "values": {"san_antonio": 7175}}
    assert score(expected, {"status": "answered", "values": {"San Antonio": 7175.0}})["correct"]


def test_score_rejects_off_by_one_wrong_status_and_missing_caveat():
    assert not score(ANSWERED, {"status": "answered", "values": {"2024": 14123}})["correct"]
    assert not score(ANSWERED, {"status": "declined", "values": {}})["correct"]
    caveat = {"status": "answered", "values": {}, "notes_must_mention": ["report"]}
    assert not score(caveat, {"status": "answered", "values": {}, "notes": "none"})["correct"]
    assert score(caveat, {"status": "answered", "values": {}, "notes": "Report date"})["correct"]
    assert not score(ANSWERED, None)["correct"]


def test_declined_ignores_values():
    assert score({"status": "declined"}, {"status": "declined", "values": {}, "notes": "x"})[
        "correct"
    ]


def test_questions_file_is_well_formed():
    questions = load_questions()
    assert len(questions) == 10
    assert len({q["id"] for q in questions}) == 10
    for q in questions:
        assert q["expected"]["status"] in {"answered", "declined"}
        assert (q["expected"]["status"] == "answered") == bool(q["expected"].get("values"))


def test_model_ref_only_allows_free_providers():
    assert str(ModelRef.parse("groq:openai/gpt-oss-120b")) == "groq:openai/gpt-oss-120b"
    for bad in ("openai:gpt-5", "anthropic:claude", "openrouter:deepseek/x", "groq"):
        with pytest.raises(ValueError):
            ModelRef.parse(bad)


def _client(handler, monkeypatch: pytest.MonkeyPatch, waits: list[float]) -> ChatClient:
    monkeypatch.setenv("GROQ_API_KEY", "test")
    return ChatClient(
        ModelRef.parse("groq:m"),
        max_attempts=3,
        sleep=waits.append,
        transport=httpx.MockTransport(handler),
    )


def test_daily_quota_429_is_not_retried(monkeypatch: pytest.MonkeyPatch):
    body = {"error": {"message": "Quota exceeded for metric generate_requests_PerDay"}}
    waits: list[float] = []
    client = _client(lambda _: httpx.Response(429, json=body), monkeypatch, waits)
    with pytest.raises(QuotaExhaustedError, match="daily"):
        client.complete([{"role": "user", "content": "x"}])
    assert waits == []


def test_quota_error_redacts_account_id(monkeypatch: pytest.MonkeyPatch):
    body = {"error": {"message": "organization `org_01abcdefghijklmnop` tokens per day (TPD)"}}
    client = _client(lambda _: httpx.Response(429, json=body), monkeypatch, [])
    with pytest.raises(QuotaExhaustedError) as err:
        client.complete([{"role": "user", "content": "x"}])
    assert "org_01abcdefghijklmnop" not in str(err.value)


def test_retries_429_using_provider_hints(monkeypatch: pytest.MonkeyPatch):
    calls = iter(
        [
            httpx.Response(429, headers={"retry-after": "7"}),
            httpx.Response(429, json={"error": {"details": [{"retryDelay": "3s"}]}}),
            httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}], "usage": {}}),
        ]
    )
    waits: list[float] = []
    client = _client(lambda _: next(calls), monkeypatch, waits)
    assert client.complete([{"role": "user", "content": "x"}])["content"] == "hi"
    assert waits == [7.0, 3.0]
    assert client.usage.rate_limited == 2


def test_persistent_429_raises_quota_error(monkeypatch: pytest.MonkeyPatch):
    waits: list[float] = []
    client = _client(lambda _: httpx.Response(429), monkeypatch, waits)
    with pytest.raises(QuotaExhaustedError):
        client.complete([{"role": "user", "content": "x"}])
    assert len(waits) == 2  # no wait after the last attempt


def test_warehouse_blocks_raw_files_and_attach(tmp_path: Path):
    db = tmp_path / "w.duckdb"
    with duckdb.connect(str(db)) as con:
        con.sql("create table stg_x as select 1 as a")
    (tmp_path / "raw.csv").write_text("name\nsecret\n")
    wh = Warehouse(db)
    assert wh.query("select a from stg_x").rows == [(1,)]
    assert "stg_x(a INTEGER)" in wh.schema_text()
    for sql in (
        f"select * from read_csv('{tmp_path / 'raw.csv'}')",
        f"attach '{tmp_path / 'other.duckdb'}' as o",
        "set enable_external_access = true",
    ):
        with pytest.raises((duckdb.Error, QueryRejectedError)):
            wh.query(sql)
    wh.close()


def test_query_accepts_one_select_only(tmp_path: Path):
    db = tmp_path / "w.duckdb"
    with duckdb.connect(str(db)) as con:
        con.sql("create table stg_x as select 1 as a")
    wh = Warehouse(db)
    for ok in ("select a from stg_x", "with t as (select 1) select * from t", "from stg_x"):
        wh.query(ok)
    for bad in (
        f"copy (select 1) to '{tmp_path / 'out.csv'}'",
        f"attach '{tmp_path / 'o.duckdb'}' as o",
        "set threads = 1",
        "create table y as select 1",
        "select 1; drop table stg_x",
        "explain select 1",
    ):
        with pytest.raises(QueryRejectedError):
            wh.query(bad)
    assert not (tmp_path / "out.csv").exists()
    wh.close()


def test_parquet_bundle_reads_only_its_folder(tmp_path: Path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    with duckdb.connect() as con:
        con.sql(f"copy (select range as a from range(4)) to '{bundle / 'stg_x.parquet'}'")
        con.sql(f"copy (select 'secret' as name) to '{tmp_path / 'raw.parquet'}'")
    wh = Warehouse(bundle)
    assert wh.row_counts() == {"stg_x": 4}
    assert wh.query("select sum(a) from stg_x").rows == [(6,)]
    with pytest.raises(duckdb.Error):
        wh.query(f"select * from read_parquet('{tmp_path / 'raw.parquet'}')")
    wh.close()
