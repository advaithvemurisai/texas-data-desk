"""Shared test builders (fixtures live in conftest.py)."""

from typing import Any

from tdd_ingest.registry import Dataset


def make_dataset(source: dict[str, Any], **overrides: Any) -> Dataset:
    fields: dict[str, Any] = {
        "id": "test_ds",
        "city": "dallas",
        "topic": "311",
        "title": "Test",
        "grain": "row",
        "date_fields": ["created"],
        "coverage": {"kind": "full"},
        "source": source,
        "portal_url": "https://example.test",
    }
    return Dataset.model_validate(fields | overrides)


def csv_text(header: list[str], rows: list[list[str]]) -> str:
    lines = [",".join(f'"{h}"' for h in header)]
    lines += [",".join(f'"{v}"' for v in row) for row in rows]
    return "\n".join(lines) + "\n"
