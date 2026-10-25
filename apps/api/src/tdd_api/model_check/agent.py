"""A single SQL agent: definitions in the prompt, quirks and SQL through tools.

Good enough to compare models on tool calling, JSON output and SQL quality. The week-2
single-agent baseline grows from this.
"""

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tdd_api.llm import ChatClient
from tdd_api.warehouse import Warehouse

CITIES = ("dallas", "austin", "san_antonio", "houston")

SYSTEM = """\
You answer questions about open data from four Texas cities (Dallas, Austin, San Antonio,
Houston) by writing DuckDB SQL against the staging tables below. Give aggregates only.

Rules:
- Follow the definitions exactly: crime is counted in NIBRS offenses, using each city's
  counting rule; 311 concepts use the exact request types listed.
- Before answering about a city, call read_notes for it: it lists that city's data traps.
- Decline (status "declined") when the data cannot answer: San Antonio 311 covers only
  the last 12 months (no trends or multi-year comparisons); Houston 311 is not available;
  cities other than the four; predictions; "why" questions; individuals or addresses.
- State caveats the definitions require in notes (for example how a city dates crime).
- Finish by calling final_answer exactly once. Do not answer in plain text.

Definitions:
{definitions}

Tables (DuckDB):
{schema}
"""

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": "Run one read-only DuckDB SQL query; returns up to 100 rows.",
            "parameters": {
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_notes",
            "description": "Read the data-quirks notes for one city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string", "enum": list(CITIES)}},
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "final_answer",
            "description": "Submit the answer. Call once, at the end.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["answered", "declined"]},
                    "values": {
                        "type": "object",
                        "description": "Each answer key (as the question's answer format "
                        "says) mapped to its number. Empty when declined.",
                        "additionalProperties": {"type": "number"},
                    },
                    "notes": {
                        "type": "string",
                        "description": "Caveats, or why the question was declined.",
                    },
                    "sql": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "The SQL behind the values.",
                    },
                },
                "required": ["status", "values", "notes"],
            },
        },
    },
]


@dataclass
class Trace:
    answer: dict[str, Any] | None = None
    steps: int = 0
    sql_calls: int = 0
    sql_errors: int = 0
    tool_errors: int = 0  # unparseable arguments, unknown tools
    plain_text_turns: int = 0  # replies with no tool call (protocol slips)
    seconds: float = 0.0
    error: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)


class Agent:
    def __init__(self, client: ChatClient, warehouse: Warehouse, root: Path, max_steps: int = 10):
        self.client = client
        self.warehouse = warehouse
        self.root = root
        self.max_steps = max_steps
        definitions = (root / "data" / "definitions.md").read_text()
        self.system = SYSTEM.format(definitions=definitions, schema=warehouse.schema_text())

    def _notes(self, city: str) -> str:
        if city not in CITIES:
            raise ValueError(f"unknown city {city!r}")
        return (self.root / "data" / "quirks" / f"{city}.md").read_text()

    def _tool(self, name: str, args: dict[str, Any], trace: Trace) -> str:
        if name == "read_notes":
            return self._notes(str(args.get("city")))
        if name == "run_sql":
            trace.sql_calls += 1
            try:
                return self.warehouse.query(str(args["sql"])).as_text()
            except Exception as exc:  # SQL errors go back to the model
                trace.sql_errors += 1
                return f"SQL error: {type(exc).__name__}: {exc}"
        raise ValueError(f"unknown tool {name!r}")

    def ask(self, question: str, keys: str) -> Trace:
        trace = Trace()
        start = time.monotonic()
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system},
            {"role": "user", "content": f"{question}\n\nAnswer keys: {keys}."},
        ]
        try:
            while trace.steps < self.max_steps and trace.answer is None:
                trace.steps += 1
                message = self.client.complete(messages, TOOLS)
                # Echo the message back unchanged: Gemini needs its thought signatures.
                messages.append(message)
                calls = message.get("tool_calls") or []
                if not calls:
                    trace.plain_text_turns += 1
                    messages.append(
                        {"role": "user", "content": "Use the tools; finish with final_answer."}
                    )
                    continue
                for call in calls:
                    fn = call.get("function", {})
                    name = fn.get("name", "")
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                        if name == "final_answer":
                            trace.answer = args
                            result = "ok"
                        else:
                            result = self._tool(name, args, trace)
                    except (json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
                        trace.tool_errors += 1
                        result = f"tool error: {exc}"
                    trace.events.append({"tool": name, "args": fn.get("arguments")})
                    messages.append(
                        {"role": "tool", "tool_call_id": call.get("id", ""), "content": result}
                    )
                    if trace.answer is not None:
                        break
        except Exception as exc:  # quota, HTTP or provider errors end this question only
            trace.error = f"{type(exc).__name__}: {exc}"[:500]
        trace.seconds = round(time.monotonic() - start, 1)
        return trace
