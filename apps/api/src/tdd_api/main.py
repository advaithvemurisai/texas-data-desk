"""FastAPI app. Vercel serves it from apps/api/app.py."""

import time
from functools import lru_cache

from fastapi import FastAPI

from tdd_api import config
from tdd_api.warehouse import Warehouse

app = FastAPI(title="Texas Data Desk API")


@lru_cache(maxsize=1)
def warehouse() -> Warehouse:
    # One read-only connection per function instance, opened on first use.
    return Warehouse(config.warehouse_path())


@app.get("/api/health")
def health() -> dict[str, object]:
    """Liveness plus a real warehouse query, so a deploy proves the bundled data loads."""
    started = time.perf_counter()
    tables = warehouse().row_counts()
    return {
        "status": "ok",
        "tables": tables,
        "query_ms": round((time.perf_counter() - started) * 1000, 1),
    }
