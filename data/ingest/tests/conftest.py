from collections.abc import Iterator

import pytest
from tdd_ingest.http import Http


@pytest.fixture
def sleeps() -> list[float]:
    return []


@pytest.fixture
def http(sleeps: list[float]) -> Iterator[Http]:
    with Http(max_attempts=3, base_wait=0.01, sleep=sleeps.append) as client:
        yield client
