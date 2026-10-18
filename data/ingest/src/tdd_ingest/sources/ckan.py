"""CKAN (San Antonio).

Pages the DataStore (`datastore_search`, sorted by _id) when the resource has one, otherwise
downloads the resource file. The package is re-read after the pull: San Antonio replaces its
datasets wholesale on upload, so a changed last_modified means the pages may mix two uploads.
"""

from collections.abc import Iterator
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlparse

import pyarrow as pa

from tdd_ingest.http import Http
from tdd_ingest.registry import CkanSource as CkanConfig
from tdd_ingest.snapshot import SnapshotWriter
from tdd_ingest.sources.base import SourceChangedError, SourceResult
from tdd_ingest.tables import iter_csv_file, records_to_table


class ResourceNotFoundError(LookupError):
    pass


class CkanSource:
    def __init__(self, cfg: CkanConfig, http: Http) -> None:
        self.cfg = cfg
        self.http = http
        self.api = cfg.base_url.rstrip("/") + "/api/3/action"

    def _action(self, name: str, **params: str) -> dict[str, Any]:
        payload = self.http.get(f"{self.api}/{name}", params=params).json()
        if not payload.get("success"):
            raise RuntimeError(f"CKAN {name} failed: {payload.get('error')}")
        return payload["result"]

    def resource(self) -> tuple[dict[str, Any], dict[str, Any]]:
        package = self._action("package_show", id=self.cfg.package)
        resources = package.get("resources", [])
        if self.cfg.resource_id:
            matches = [r for r in resources if r["id"] == self.cfg.resource_id]
        else:
            want = self.cfg.resource_name.casefold()
            matches = [r for r in resources if (r.get("name") or "").casefold() == want]
        if len(matches) != 1:
            names = [f"{r.get('name')} ({r['id']})" for r in resources]
            raise ResourceNotFoundError(
                f"package {self.cfg.package!r}: expected one resource matching "
                f"{self.cfg.resource_id or self.cfg.resource_name!r}, found {len(matches)}. "
                f"Resources: {names}"
            )
        resource = matches[0]
        if self.cfg.resource_name.casefold() != (resource.get("name") or "").casefold():
            raise ResourceNotFoundError(
                f"pinned resource {resource['id']} is now named {resource.get('name')!r}, "
                f"not {self.cfg.resource_name!r}; check the portal and update the registry"
            )
        return package, resource

    def datastore_pages(
        self, resource_id: str, columns: list[str], total: int
    ) -> Iterator[pa.Table]:
        offset = 0
        while offset < total:
            result = self._action(
                "datastore_search",
                resource_id=resource_id,
                limit=str(self.cfg.page_size),
                offset=str(offset),
                sort="_id",
                include_total="false",
            )
            records = result.get("records", [])
            if not records:
                return
            yield records_to_table(records, columns)
            offset += len(records)

    def fetch(self, writer: SnapshotWriter) -> SourceResult:
        package, resource = self.resource()
        stamp_before = resource.get("last_modified") or package.get("metadata_modified")
        warnings: list[str] = []
        requests: dict[str, Any] = {"package": self.cfg.package, "resource_id": resource["id"]}

        if resource.get("datastore_active"):
            head = self._action("datastore_search", resource_id=resource["id"], limit="0")
            expected = int(head["total"])
            columns = [f["id"] for f in head["fields"] if f["id"] != "_id"]
            writer.write_part("part-00000", self.datastore_pages(resource["id"], columns, expected))
            requests |= {
                "method": "datastore_search",
                "sort": "_id",
                "page_size": self.cfg.page_size,
            }
        else:
            name = PurePosixPath(urlparse(resource["url"]).path).name or f"{resource['id']}.csv"
            dest = writer.original_dir / name
            response = self.http.download(resource["url"], dest)
            writer.add_original(dest, origin=str(response.url))
            writer.write_part("part-00000", iter_csv_file(dest))
            expected = None
            requests |= {"method": "resource download", "url": resource["url"]}
            warnings.append("DataStore inactive; downloaded the resource file (no source count)")

        package_after, resource_after = self.resource()
        stamp_after = resource_after.get("last_modified") or package_after.get("metadata_modified")
        if stamp_before != stamp_after:
            raise SourceChangedError(
                f"{self.cfg.package} was re-uploaded during the pull "
                f"({stamp_before} -> {stamp_after})"
            )
        return SourceResult(
            expected_count=expected,
            freshness={
                "resource_last_modified": resource_after.get("last_modified"),
                "package_metadata_modified": package_after.get("metadata_modified"),
                "resource_name": resource_after.get("name"),
                "license_id": package_after.get("license_id"),
            },
            requests=requests,
            warnings=warnings,
        )
