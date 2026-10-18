"""Locating the repo and loading local settings."""

import os
from pathlib import Path


def repo_root(start: Path | None = None) -> Path:
    """The repo root: the nearest parent holding data/registry.yaml, or $TDD_ROOT."""
    if env := os.environ.get("TDD_ROOT"):
        return Path(env).resolve()
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "data" / "registry.yaml").is_file():
            return candidate
    raise RuntimeError(
        "Could not find data/registry.yaml. Run from inside the repo or set TDD_ROOT."
    )


def registry_path(root: Path) -> Path:
    return root / "data" / "registry.yaml"


def raw_root(root: Path) -> Path:
    return root / "data" / "raw"


def load_dotenv(root: Path) -> None:
    """Read KEY=VALUE lines from <root>/.env without overriding the real environment."""
    env_file = root / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("'\"")
        if value:
            os.environ.setdefault(key.strip(), value)
