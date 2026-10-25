"""tdd-model-check: run the week-1 model test and score each model."""

import json
import logging
import statistics
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml
from tdd_ingest import paths

from tdd_api.llm import ChatClient, ModelRef, QuotaExhaustedError
from tdd_api.model_check.agent import Agent, Trace
from tdd_api.warehouse import Warehouse

QUESTIONS = Path(__file__).with_name("questions.yaml")
DEFAULT_MODELS = [
    "gemini:gemini-3.8-flash",
    "gemini:gemini-3.5-flash",
    "gemini:gemini-3.5-flash-lite",
    "groq:openai/gpt-oss-120b",
    "groq:qwen/qwen3.8-27b",
]

app = typer.Typer(no_args_is_help=True, add_completion=False)


def load_questions() -> list[dict[str, Any]]:
    return yaml.safe_load(QUESTIONS.read_text())["questions"]


def _norm_key(key: object) -> str:
    return str(key).strip().lower().replace(" ", "_")


def score(expected: dict[str, Any], answer: dict[str, Any] | None) -> dict[str, bool]:
    """Status, exact values per key, and required caveats; correct only if all hold."""
    if not isinstance(answer, dict):
        return {"status": False, "values": False, "notes": False, "correct": False}
    status_ok = answer.get("status") == expected["status"]
    values_ok = True
    if expected["status"] == "answered":
        got_raw = answer.get("values")
        got = {_norm_key(k): v for k, v in got_raw.items()} if isinstance(got_raw, dict) else {}
        values_ok = all(
            isinstance(got.get(_norm_key(k)), int | float) and got[_norm_key(k)] == v
            for k, v in expected["values"].items()
        )
    notes = str(answer.get("notes", "")).lower()
    notes_ok = all(word.lower() in notes for word in expected.get("notes_must_mention", []))
    return {
        "status": status_ok,
        "values": values_ok,
        "notes": notes_ok,
        "correct": status_ok and values_ok and notes_ok,
    }


def _row(question: dict[str, Any], trace: Trace) -> dict[str, Any]:
    return {
        "id": question["id"],
        "score": score(question["expected"], trace.answer),
        "answer": trace.answer,
        "steps": trace.steps,
        "sql_calls": trace.sql_calls,
        "sql_errors": trace.sql_errors,
        "tool_errors": trace.tool_errors,
        "plain_text_turns": trace.plain_text_turns,
        "seconds": trace.seconds,
        "error": trace.error,
        "events": trace.events,
    }


def run_model(
    ref: ModelRef, questions: list[dict[str, Any]], root: Path, warehouse: Warehouse
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    with ChatClient(ref) as client:
        agent = Agent(client, warehouse, root)
        for q in questions:
            typer.echo(f"  {ref} {q['id']} ...", nl=False)
            trace = agent.ask(q["question"], q["keys"])
            row = _row(q, trace)
            rows.append(row)
            mark = "ok" if row["score"]["correct"] else "WRONG"
            typer.echo(
                f" {mark} ({trace.steps} steps, {trace.seconds}s){' ' + (trace.error or '')}"
            )
            if trace.error and trace.error.startswith(QuotaExhaustedError.__name__):
                typer.secho(
                    f"  {ref}: quota exhausted, skipping its remaining questions", fg="yellow"
                )
                break
        usage = client.usage
    return {
        "model": str(ref),
        "correct": sum(r["score"]["correct"] for r in rows),
        "asked": len(rows),
        "usage": vars(usage),
        "questions": rows,
    }


def summary_table(results: list[dict[str, Any]]) -> str:
    lines = [
        "| Model | Correct | Wrong status | Wrong values | Missing caveat | Tool errors "
        "| Plain-text turns | SQL errors | Requests | Tokens | 429s | Errors | Median s/question |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        qs = r["questions"]
        u = r["usage"]
        lines.append(
            f"| {r['model']} | {r['correct']}/{r['asked']} "
            f"| {sum(not q['score']['status'] for q in qs)} "
            f"| {sum(q['score']['status'] and not q['score']['values'] for q in qs)} "
            f"| {sum(not q['score']['notes'] for q in qs)} "
            f"| {sum(q['tool_errors'] for q in qs)} | {sum(q['plain_text_turns'] for q in qs)} "
            f"| {sum(q['sql_errors'] for q in qs)} | {u['requests']} | {u['total_tokens']:,} "
            f"| {u['rate_limited']} | {sum(bool(q['error']) for q in qs)} "
            f"| {statistics.median(q['seconds'] for q in qs) if qs else 0:.0f} |"
        )
    return "\n".join(lines)


def _shown(path: Path, root: Path) -> str:
    return str(path.relative_to(root)) if path.is_relative_to(root) else str(path)


@app.command()
def run(
    models: Annotated[list[str] | None, typer.Argument(help="<provider>:<model id>")] = None,
    only: Annotated[list[str] | None, typer.Option(help="Question ids to run")] = None,
    out_dir: Annotated[Path | None, typer.Option(help="Where results JSON go")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Run the model test on the LIVE warehouse (never the eval one); one JSON per model."""
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    root = paths.repo_root()
    paths.load_dotenv(root)
    refs = [ModelRef.parse(m) for m in models or DEFAULT_MODELS]
    questions = [q for q in load_questions() if not only or q["id"] in only]
    out_dir = out_dir or root / "docs" / "model_check"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%SZ")
    warehouse = Warehouse(root / "data" / "warehouse_live.duckdb")
    for ref in refs:
        result = run_model(ref, questions, root, warehouse)
        result["run_at"] = stamp
        slug = str(ref).replace(":", "_").replace("/", "_")
        path = out_dir / f"{stamp}-{slug}.json"
        path.write_text(json.dumps(result, indent=2, default=str))
        typer.echo(f"wrote {_shown(path, root)}")
    warehouse.close()


@app.command()
def summary(files: Annotated[list[Path], typer.Argument(help="Results JSON files")]) -> None:
    """Print one markdown table row per results file."""
    typer.echo(summary_table([json.loads(f.read_text()) for f in files]))
