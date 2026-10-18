from dataclasses import dataclass, field
from typing import Any, Protocol

from tdd_ingest.snapshot import SnapshotWriter


class SourceChangedError(RuntimeError):
    """The portal republished the dataset while we were pulling it; the pull must restart."""


@dataclass
class SourceResult:
    expected_count: int | None
    freshness: dict[str, Any]
    requests: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


class Source(Protocol):
    def fetch(self, writer: SnapshotWriter) -> SourceResult:
        """Write every part (and any originals) into writer and describe what was pulled."""
        ...
