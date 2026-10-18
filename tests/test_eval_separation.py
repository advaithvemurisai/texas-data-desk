"""CLAUDE.md rule 3: agent code, data tooling, registry and quirks never reference evals/."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARDED = [ROOT / "apps", ROOT / "data"]
SKIP_DIRS = {"raw", "manual", "node_modules", ".next", "target", "logs", "__pycache__", ".venv"}
TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".md",
    ".yaml",
    ".yml",
    ".sql",
    ".json",
    ".toml",
}
EVALS_REF = re.compile(r"(^|[^\w-])evals([/\\.]|\b)")


def guarded_files() -> list[Path]:
    files = []
    for base in GUARDED:
        for path in base.rglob("*"):
            skipped = SKIP_DIRS.intersection(path.relative_to(ROOT).parts)
            if path.is_file() and path.suffix in TEXT_SUFFIXES and not skipped:
                files.append(path)
    return files


def test_no_references_to_evals() -> None:
    offenders = [
        f"{path.relative_to(ROOT)}:{n}"
        for path in guarded_files()
        for n, line in enumerate(path.read_text(errors="ignore").splitlines(), 1)
        if EVALS_REF.search(line)
    ]
    assert not offenders, f"files under apps/ or data/ reference evals: {offenders}"


def test_pattern_catches_imports_and_paths() -> None:
    for bad in ("from evals.gold import x", "open('evals/gold/q1.sql')", "import evals"):
        assert EVALS_REF.search(bad)
    for ok in ("retrievals", "evaluation", "tdd-evals-free"):
        assert not EVALS_REF.search(ok)
