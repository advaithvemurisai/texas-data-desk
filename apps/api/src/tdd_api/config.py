"""Where the API finds its warehouse and keys, locally and on Vercel.

On Vercel the warehouse is bundled as one Parquet file per staging table in
apps/api/data/warehouse/ (exported by scripts/stage_warehouse.sh before each deploy) and keys
come from project environment variables. Locally it falls back to the repo's live warehouse
and reads .env.
"""

import os
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[2]  # apps/api
BUNDLED_WAREHOUSE = API_ROOT / "data" / "warehouse"  # stg_*.parquet


def repo_root() -> Path | None:
    """The repo root when running from a checkout (it holds data/registry.yaml), else None."""
    for candidate in (API_ROOT, *API_ROOT.parents):
        if (candidate / "data" / "registry.yaml").is_file():
            return candidate
    return None


def warehouse_path() -> Path:
    """$TDD_WAREHOUSE, else the bundled copy, else the checkout's live warehouse."""
    if env := os.environ.get("TDD_WAREHOUSE"):
        return Path(env)
    if any(BUNDLED_WAREHOUSE.glob("stg_*.parquet")):
        return BUNDLED_WAREHOUSE
    root = repo_root()
    return (root or API_ROOT) / "data" / "warehouse_live.duckdb"


def load_dotenv() -> None:
    """Read KEY=VALUE lines from the checkout's .env without overriding the environment."""
    root = repo_root()
    env_file = root / ".env" if root else None
    if not env_file or not env_file.is_file():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.split(" #", 1)[0].strip().strip("'\"")
        if value:
            os.environ.setdefault(key.strip(), value)
