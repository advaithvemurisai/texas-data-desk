"""Socrata (Dallas, Austin).

Rows are paged by keyset on the system :id column (`$where=:id > '<last>'`, `$order=:id`).
Offset paging can skip or repeat rows on a dataset that changes during the pull. These
portals also reload whole datasets on refresh, which reassigns every :id, so rowsUpdatedAt
is compared before and after and a pull that straddles a reload is rejected.
"""

from collections.abc import Iterator
from typing import Any

import pyarrow as pa

from tdd_ingest.http import Http
from tdd_ingest.registry import SocrataSource as SocrataConfig
from tdd_ingest.snapshot import SnapshotWriter
from tdd_ingest.sources.base import SourceChangedError, SourceResult
from tdd_ingest.tables import csv_bytes_to_table

SELECT_ALL = ":*,*"  # system fields (:id, :created_at, :updated_at, :version), then all columns


class SocrataSource:
    def __init__(self, cfg: SocrataConfig, http: Http, app_token: str | None = None) -> None:
        self.cfg = cfg
        self.http = http
        self.headers = {"X-App-Token": app_token} if app_token else {}
        self.base = f"https://{cfg.domain}"

    @property
    def resource_url(self) -> str:
        return f"{self.base}/resource/{self.cfg.dataset_id}"

    def metadata(self) -> dict[str, Any]:
        url = f"{self.base}/api/views/{self.cfg.dataset_id}.json"
        return self.http.get(url, headers=self.headers).json()

    def count(self) -> int:
        rows = self.http.get(
            f"{self.resource_url}.json", params={"$select": "count(*)"}, headers=self.headers
        ).json()
        return int(rows[0]["count"])

    def pages(self) -> Iterator[pa.Table]:
        last_id: str | None = None
        while True:
            params = {"$select": SELECT_ALL, "$order": ":id", "$limit": str(self.cfg.page_size)}
            if last_id is not None:
                params["$where"] = f":id > '{last_id}'"
            body = self.http.get(f"{self.resource_url}.csv", params=params, headers=self.headers)
            table = csv_bytes_to_table(body.content)
            if table.num_rows == 0:
                return
            yield table
            if table.num_rows < self.cfg.page_size:
                return
            last_id = table.column(":id")[-1].as_py()

    def fetch(self, writer: SnapshotWriter) -> SourceResult:
        before = self.metadata()
        expected = self.count()
        writer.write_part("part-00000", self.pages())
        after = self.metadata()
        if before.get("rowsUpdatedAt") != after.get("rowsUpdatedAt"):
            raise SourceChangedError(
                f"{self.cfg.dataset_id} was refreshed during the pull "
                f"(rowsUpdatedAt {before.get('rowsUpdatedAt')} -> {after.get('rowsUpdatedAt')})"
            )
        return SourceResult(
            expected_count=expected,
            freshness={
                "rowsUpdatedAt": after.get("rowsUpdatedAt"),
                "viewLastModified": after.get("viewLastModified"),
                "name": after.get("name"),
                "licenseId": after.get("licenseId"),
            },
            requests={
                "url": f"{self.resource_url}.csv",
                "select": SELECT_ALL,
                "order": ":id",
                "page_size": self.cfg.page_size,
                "pagination": "keyset on :id",
                "app_token": bool(self.headers),
            },
        )
