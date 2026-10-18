"""Typed view of data/registry.yaml."""

from datetime import date
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

City = Literal["dallas", "austin", "san_antonio", "houston"]
Topic = Literal["311", "crime", "shelter"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Coverage(_Model):
    kind: Literal["full", "rolling_365d", "ends_at"]
    start: date | None = None
    end: date | None = None


class SocrataSource(_Model):
    type: Literal["socrata"]
    domain: str
    dataset_id: Annotated[str, Field(pattern=r"^[a-z0-9]{4}-[a-z0-9]{4}$")]
    page_size: Annotated[int, Field(gt=0, le=50_000)] = 50_000


class CkanSource(_Model):
    type: Literal["ckan"]
    base_url: str
    package: str
    resource_name: str
    # Pinned after the first run so a renamed or replaced resource fails loudly.
    resource_id: str | None = None
    page_size: Annotated[int, Field(gt=0, le=32_000)] = 32_000


class CsvFile(_Model):
    label: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]+$")]
    url: str | None = None
    # Relative to the repo root; used when the URL is blocked or missing.
    manual_path: str | None = None

    @model_validator(mode="after")
    def _has_a_location(self) -> "CsvFile":
        if not (self.url or self.manual_path):
            raise ValueError(f"file {self.label!r} needs a url or a manual_path")
        return self


class CsvSource(_Model):
    type: Literal["csv"]
    encoding: str = "utf-8"
    files: Annotated[list[CsvFile], Field(min_length=1)]

    @model_validator(mode="after")
    def _unique_labels(self) -> "CsvSource":
        labels = [f.label for f in self.files]
        if len(labels) != len(set(labels)):
            raise ValueError("csv file labels must be unique")
        return self


SourceConfig = Annotated[SocrataSource | CkanSource | CsvSource, Field(discriminator="type")]


class Dataset(_Model):
    id: Annotated[str, Field(pattern=r"^[a-z0-9_]+$")]
    city: City
    topic: Topic
    title: str
    grain: str
    # Candidate columns for the dataset's analysis date, first match wins
    # (Houston renamed its occurrence-date column between yearly files).
    date_fields: list[str] = []
    coverage: Coverage
    source: SourceConfig
    portal_url: str
    license: str | None = None
    pii_columns: list[str] = []
    notes: str | None = None


class Registry(_Model):
    datasets: list[Dataset]

    @model_validator(mode="after")
    def _unique_ids(self) -> "Registry":
        ids = [d.id for d in self.datasets]
        if len(ids) != len(set(ids)):
            raise ValueError("dataset ids must be unique")
        return self

    def get(self, dataset_id: str) -> Dataset:
        for ds in self.datasets:
            if ds.id == dataset_id:
                return ds
        known = ", ".join(d.id for d in self.datasets)
        raise KeyError(f"unknown dataset {dataset_id!r} (known: {known})")


def load_registry(path: Path) -> Registry:
    return Registry.model_validate(yaml.safe_load(path.read_text()))
