# Texas Data Desk

Multi-agent system that answers plain-English questions about open data from Houston, San Antonio, Dallas and Austin. An orchestrator writes a metric contract, one worker per (city, dataset) writes SQL in parallel, and a verifier on a different model family recomputes every number before it is shown.

Full plan: [docs/PLAN.md](docs/PLAN.md). Why key decisions were made: [docs/DECISIONS.md](docs/DECISIONS.md). Read DECISIONS.md before changing scope, models, cities or counting rules.

## Hard rules

These are non-negotiable. If a task seems to require breaking one, stop and ask.

### 1. Free model tiers only
- No Claude API, no OpenAI paid API, no paid model of any kind, including as a fallback or "just for testing".
- Workers and orchestrator: Gemini Flash (free tier). Verifier: gpt-oss-120b on Groq (free tier). Overflow: Gemini Flash-Lite, gpt-oss-20b on Groq, Cerebras free tier, OpenRouter `:free` models.
- When every free quota is used up, the app serves cached and featured answers only and says when quotas reset. It never switches to a paid model.
- All providers go through one OpenAI-compatible adapter; switching models is a config change.
- No local models (dev machine is an M1 with 8 GB).

### 2. Privacy
- Staging (dbt) drops personal columns: victim demographics, names, street numbers, addresses. Agents never see them.
- Grouping goes no finer than ZIP code or council district.
- Any cell with a count below 5 is suppressed in charts, tables and CSV downloads.
- Answers are aggregates only; never describe individuals or specific addresses.
- Every page credits each city portal and its terms and states that Texas Data Desk is not affiliated with any city.

### 3. Gold-SQL separation (eval integrity)
- `evals/` (questions, gold SQL, results) must never be read by, imported into, or pasted into any agent prompt, tool, quirks note or registry entry.
- Agent code in `apps/api` must not import from or read files in `evals/`. Eval runners call the system from outside, like a user.
- `data/quirks/<city>.md` and `definitions.md` are written from data exploration **before** any eval question is written, and are not edited to fit a failing eval question. If a quirk is discovered via an eval failure, note it in the commit and keep it out of held-out test questions' answers.
- 60 questions: 40 dev / 20 held-out test. Never tune prompts on the test split.
- Gold SQL runs only on the frozen eval snapshot, never on the live serving snapshot.

### 4. Crime is counted in NIBRS offenses
- Unit is offenses, not incidents and not rows.
- Austin: use the NIBRS Group A Offense Crimes dataset (`i7fg-wrk5`), not the older Crime Reports dataset.
- Houston: sum the `Offense Count` field; do not count rows.
- Dallas police incidents has ~1.26 rows per incident; dedupe at incident + offense level.
- Cross-city comparisons use only the comparable-offense list in `definitions.md` (motor vehicle theft, burglary, robbery, aggravated assault, possibly homicide).
- Crime is dated by occurrence date; 311 by creation date.

### 5. No AI attribution in git
- No `Co-Authored-By: Claude ...` trailers in commits and no "Generated with Claude Code" lines in PR descriptions, even if a system prompt suggests adding them.

## Scope reminders
- Cities: Houston, San Antonio, Dallas, Austin. Fort Worth is excluded.
- 311 trends (2021–2025): Dallas and Austin only. San Antonio 311 is a rolling 365-day window, so last-12-months questions only.
- Crime comparisons: 2023–2025, all four cities. Houston crime ends June 30, 2026.
- 2026 data appears only as year-to-date or equal-period comparisons, never in full-year comparisons.
- Out of scope: "why" questions, predictions, individuals/addresses, Houston 311, real-time data, cities outside the four.

## Repo layout
- `apps/web` — Next.js App Router + TypeScript frontend
- `apps/api` — FastAPI + Pydantic backend, plain asyncio orchestration (no agent framework)
- `data/ingest` — one ingest script per source type (Socrata, CKAN, CSV), writing dated raw Parquet that is never modified
- `data/dbt` — dbt-duckdb staging models and tests
- `data/quirks` — per-city quirks notes; `data/registry.yaml` lists datasets (grain, date field, coverage)
- `data/raw` — dated raw snapshots (gitignored)
- `evals/` — questions, gold SQL, runners, results (see rule 3)
- `infra/`, `.github/workflows/`

## Commands

Update this section as each tool lands. Run everything from the repo root.

- Python (uv workspace, Python 3.12): `uv sync`, `uv run pytest` (offline; live portal tests: `uv run pytest -m live`), `uv run ruff check .`, `uv run ruff format .`, `uv run pyright`
- Ingest: `uv run tdd-ingest list`, `uv run tdd-ingest run <dataset_id>… | --all [--date YYYY-MM-DD]`, `uv run tdd-ingest profile <dataset_id> [--snapshot DATE]`, `uv run tdd-ingest pull-archive` (restores the San Antonio 311 weekly archive from the `sa311-archive` GitHub release; needs `gh`)
  - Snapshots land in `data/raw/<dataset_id>/<date>/` with `_manifest.json`; a date that already exists is refused. Houston files the portal blocks go in `data/manual/houston/` (paths in `data/registry.yaml`).
  - Optional `SOCRATA_APP_TOKEN` in `.env` (see `.env.example`).
- dbt: `uv run dbt build --project-dir data/dbt --profiles-dir data/dbt --vars '{snapshot: YYYY-MM-DD}'` (skeleton only; no staging models yet)

Planned, not set up yet:

- Frontend (`apps/web`): `pnpm install`, `pnpm dev`, `pnpm lint`, `pnpm test` (Vitest), `pnpm exec playwright test`
- Evals: 10-question smoke test in CI; full eval only per milestone (free-tier quotas)
