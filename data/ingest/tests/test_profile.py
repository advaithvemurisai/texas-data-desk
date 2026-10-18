from datetime import date
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from helpers import make_dataset
from tdd_ingest.profile import profile


def test_profile_flags_gaps_swings_and_impossible_dates(tmp_path: Path):
    snap = tmp_path / "2026-10-17"
    snap.mkdir()
    dates = (
        ["2024-01-05T00:00:00.000"] * 100
        + ["2024-03-02T00:00:00.000"] * 100  # February 2024 is a gap
        + ["2025-01-09T00:00:00.000"] * 200  # +100% vs January 2024
        + ["2920-01-01T00:00:00.000", None]  # impossible date, blank
    )
    pq.write_table(pa.table({"created": pa.array(dates, pa.string())}), snap / "part-00000.parquet")
    ds = make_dataset(
        {"type": "socrata", "domain": "x", "dataset_id": "abcd-1234"},
        coverage={"kind": "full", "start": date(2020, 1, 1)},
    )

    out = profile(ds, snap)

    assert "402 rows" in out
    assert "2024-02          0  GAP" in out
    assert "2025-01        200  YoY +100%" in out
    assert "unparseable/blank: 1" in out
    assert "outside 2020-01-01 … 2026-10-17: 1" in out


def test_profile_coalesces_renamed_date_columns(tmp_path: Path):
    snap = tmp_path / "2026-10-17"
    snap.mkdir()
    pq.write_table(pa.table({"RMSOccurrenceDate": ["1/2/2023"] * 3}), snap / "part-2023.parquet")
    pq.write_table(pa.table({"Occurrence Date": ["2026-01-01"] * 2}), snap / "part-2026.parquet")
    ds = make_dataset(
        {"type": "csv", "files": [{"label": "x", "url": "https://x"}]},
        date_fields=["RMSOccurrenceDate", "Occurrence Date"],
    )

    out = profile(ds, snap)

    assert "min 2023-01-02" in out
    assert "max 2026-01-01" in out
    assert "unparseable/blank: 0" in out
