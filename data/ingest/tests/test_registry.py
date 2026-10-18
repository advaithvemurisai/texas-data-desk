from pathlib import Path

import pytest
from helpers import make_dataset
from pydantic import ValidationError
from tdd_ingest.registry import load_registry

REGISTRY = Path(__file__).resolve().parents[2] / "registry.yaml"


def test_repo_registry_is_valid():
    registry = load_registry(REGISTRY)
    ids = {d.id for d in registry.datasets}
    assert {"dallas_311", "austin_nibrs", "sa_311", "houston_nibrs"} <= ids
    assert {d.city for d in registry.datasets} == {"dallas", "austin", "san_antonio", "houston"}
    # CLAUDE.md rule 4: Austin crime must come from the NIBRS Group A dataset.
    assert registry.get("austin_nibrs").source.model_dump()["dataset_id"] == "i7fg-wrk5"


def test_unknown_source_type_rejected():
    with pytest.raises(ValidationError):
        make_dataset({"type": "arcgis", "url": "https://x"})


def test_bad_socrata_id_rejected():
    with pytest.raises(ValidationError):
        make_dataset({"type": "socrata", "domain": "x", "dataset_id": "not-an-id"})


def test_csv_file_needs_a_location():
    with pytest.raises(ValidationError, match="url or a manual_path"):
        make_dataset({"type": "csv", "files": [{"label": "2023"}]})


def test_unknown_city_rejected():
    with pytest.raises(ValidationError):
        make_dataset(
            {"type": "socrata", "domain": "x", "dataset_id": "abcd-1234"}, city="fort_worth"
        )


def test_get_unknown_id_lists_known():
    with pytest.raises(KeyError, match="dallas_311"):
        load_registry(REGISTRY).get("nope")
