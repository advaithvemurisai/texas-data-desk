# Texas Data Desk — Project Plan

Oct 17, 2026 · @Advaith

> Exported from the Claude Docs plan (https://claude.ai/code/artifact/d466b291-287c-4557-8df5-01eb680361d5) on 2026-10-17. The two diagrams are reproduced as text.

## Overview

Texas Data Desk answers plain-English questions about the four largest Texas cities' open data. Analyst agents query each city's records in parallel, and a fact-checker agent independently recomputes every number before it is shown.

- **Who it's for:** local journalists, city council staff, civic groups and curious residents.
- **The problem:** answers like "which city's pothole requests grew fastest?" aren't published anywhere. They must be computed from millions of raw records spread across different portals with different category names, date conventions and data errors.
- **Why Google and general chatbots fall short:** search returns pages, not computed answers. Chatbots can't pull millions of rows into a chat, rarely check that definitions match across cities, and don't verify their own queries.

**Goals**

1. Correct, reproducible answers with the exact queries shown.
2. Measured proof that the multi-agent design (workers + verifier) beats a single agent, or an honest report if it doesn't.
3. A polished public demo that runs entirely on free model tiers, with no paid models at any stage.

## Scope

v1 covers four cities (Houston, San Antonio, Dallas, Austin), three topics, and fixed comparison years. Fort Worth is excluded: its portal has 10 datasets, none updated since July 2025.

| Topic | Cities | Comparison years | Notes |
| --- | --- | --- | --- |
| 311 trends | Dallas, Austin | 2021–2025 | Compare relative change, not levels; Austin's 2023 jump flagged |
| 311, last 12 months | Dallas, Austin, San Antonio | Rolling 12 months to snapshot | San Antonio publishes only the past 365 days |
| Crime | All 4 | 2023–2025 | Comparable offenses only, counted as NIBRS offenses |
| Animal shelter | Dallas | Oct 2023 → snapshot | Stretch goal |

2026 data appears as "year to date" (a dashed line, with its end month) and in equal-period questions such as "first half 2026 vs. first half 2025." It is never used in full-year comparisons.

**Question pattern:** [measure] of [what] in [where] over [when], optionally compared, ranked or per capita.

**In scope**

- Counts, trends, rankings, shares, per-capita rates, cross-city comparisons, seasonality.
- Resolution time (where closed dates exist).
- Combining datasets within one city (e.g. 311 stray-animal calls vs. shelter intake).

**Out of scope (declined, with what is available instead)**

- Why something happened, predictions, opinions and policy.
- Individuals or addresses (answers are aggregates only).
- Real-time data, neighborhood maps (v2), Houston 311, cities outside the four.

## Data sources and known pitfalls

All sources were checked live on Oct 17, 2026. Three source types are involved: Socrata (Dallas, Austin), CKAN (San Antonio) and yearly CSV downloads (Houston).

| City | Dataset | Platform | Coverage | Rows |
| --- | --- | --- | --- | --- |
| Dallas | 311 Service Requests (d7e7-envw) | Socrata | Oct 2020 → today | 2.68M |
| Dallas | Police Incidents (qv6i-rri7) | Socrata | To Oct 16, 2026 | 1.53M |
| Dallas | Animal Shelter FY23–26 (uyte-zi7f) | Socrata | Oct 2023 → today | 126k |
| Austin | 311 Unified Data (xwdj-i9he) | Socrata | Jan 2014 → today | 2.57M |
| Austin | NIBRS Group A Offense Crimes (i7fg-wrk5) | Socrata | Coverage to check in week 1 | To check |
| San Antonio | 311 All Service Calls | CKAN | Rolling past 365 days | 507k |
| San Antonio | SAPD Offenses (NIBRS) | CKAN | Jan 2023 → Sep 30, 2026 | 549k |
| Houston | HPD NIBRS yearly CSVs | CSV download | 2019 → Jun 30, 2026 | ~99k (2026 file) |

**Verified pitfalls the system must handle**

| Pitfall | Evidence | Rule |
| --- | --- | --- |
| San Antonio 311 is a rolling window | Portal note: "past 365 days"; 2024 = 940 rows, 2026 = 407k | No San Antonio 311 trends; archive it weekly from week 1 |
| Dallas crime duplicates | 2024: 134,586 rows vs 106,994 distinct incidents | Dedupe at incident + offense level |
| Austin 311 break in 2023 | 204k (2022) → 354k (2023) → 290k (2024) | Flag year-over-year swings above ±40%; find the cause |
| Austin city field is messy | AUSTIN, Austin, austin, blank, PFLUGERVILLE | Normalize casing; filter to city limits |
| Impossible dates | Dallas shelter record dated 2920; police dates from 1967 | Filter in staging; never report |
| Houston 311 unavailable | City map services return "not started" | Trap question; recheck in week 1 |
| Houston crime lag | Newest record Jun 30, 2026 | Crime comparisons end at June 2026 |

Crime is counted in **offenses**, the NIBRS standard. Austin uses its NIBRS Group A dataset (not the older Crime Reports dataset) so categories match Houston and San Antonio. Houston rows carry an `Offense Count` field, so offenses are summed, not rows counted. Cross-city comparisons use only the comparable-offense list in `definitions.md`: motor vehicle theft, burglary, robbery, aggravated assault and possibly homicide.

## Analysis rules

These rules are applied by code and stated in every answer they affect.

- **Canonical definitions:** `definitions.md`, written before any eval question, lists the exact categories per city for each concept (noise, potholes, illegal dumping, auto theft…) and the comparable-offense mapping. Gold SQL follows it.
- **Date fields:** crime by occurrence date, 311 by creation date.
- **Incomplete recent data:** the last 60 days before the snapshot are excluded (late reports); Houston crime ends June 30, 2026.
- **Small numbers:** raw counts always shown beside percentages; no % change reported on fewer than 50 records.
- **Resolution time:** only requests opened at least 90 days before the snapshot, measured as closed within 90 days.
- **Breaks in the data:** a year-over-year swing above ±40% is flagged and explained, not reported as a trend.
- **Per capita:** Census city estimates per year; 2026 uses the latest available estimate.
- **No causal claims:** district-level comparisons are correlations, and answers say so.

## Privacy and attribution

Agents never see personal data, and answers never describe individuals.

- Staging drops personal columns: victim demographics, names, street numbers and addresses.
- Grouping is allowed down to ZIP code or council district only.
- Any cell with a count below 5 is hidden in charts, tables and CSV downloads.
- Every page credits each city portal and its terms, and states that Texas Data Desk is not affiliated with any of the cities.

## Agent architecture

An orchestrator defines the question precisely, one worker per city × dataset queries the data in parallel, and a verifier on a different model checks both the definition and the numbers.

**Agent flow: every number is recomputed before it reaches the answer card**

```
                         User question
                               │
                               ▼
        ┌──────────────────────────────────────────────┐
        │ Orchestrator · Gemini Flash-Lite             │
        │ Writes the metric contract: categories,      │
        │ dates, counting unit, normalization;         │
        │ picks the workers                            │
        └──────────────────────────────────────────────┘
                               │  in parallel
     ┌──────────────┬──────────┴───┬──────────────────┐
     ▼              ▼              ▼                  ▼
  Dallas          Austin        San Antonio         Houston
  311 · crime ·   311 · crime   311 (12 mo) ·       crime only (CSV)
  shelter                       crime
  own schema +    own schema +  own schema +        own schema +
  quirks          quirks        quirks              quirks
     │              │              │                  │
     └──────────────┴──────┬───────┴──────────────────┘
                           │  value + SQL + caveats
                           ▼
        ┌──────────────────────────────────────────────┐
        │ Verifier · qwen3.8-27b on Groq               │
        │ 1. Reviews the contract against the question │
        │ 2. Code checks: coverage, duplicates,        │
        │    outliers                                  │
        │ 3. Recomputes with its own query, never sees │
        │    the worker SQL                            │
        └──────────────────────────────────────────────┘
              │                 (retry once if disputed → back to worker)
              ▼
        Answer card: headline · chart · status · table · method · sources
```

Workers each see only their own city's schema and quirks notes, which keeps contexts small. A disputed worker gets one retry; after that, the disagreement is shown to the user.

- **Metric contract** (structured JSON): categories per city, date field, date range, counting unit, normalization, exclusions. It drives the workers, the verifier and the "Interpreted as" bar.
- **Worker split rule:** one worker per (city, dataset). A Dallas-only question about two datasets gets two workers.
- **Why multi-agent:** separate contexts per city, parallel queries, and independent checking by a different model family.

**Call budget: about 8–10 model calls per question.** On free tiers, calls and tokens per question are the bottleneck, not cost (measured limits: `docs/model_check/README.md`).

| Step | Calls |
| --- | --- |
| Orchestrator writes the contract | 1 |
| Each worker writes SQL, plus one repair if it errors | 1–2 per worker |
| Verifier reviews the contract and recomputes | 1 per worker |

- Each worker's prompt already contains its city's schema, data dictionary and **full category catalog with counts** (hundreds of 311 types and offense codes), precomputed by code. No exploratory tool calls, and the per-city context is large enough for isolation to matter.
- Workers can run on different free providers at once to spread rate limits; requests beyond the limit wait in a queue.
- Expected time on free tiers: about 1–2 minutes per new question; cached and featured answers are instant.
- Temperature 0 (and fixed seeds where supported), so repeated runs measure real instability, not sampling noise.
- **When worker and verifier disagree:** code runs both queries, and the answer shows both figures with their definitions. Neither model is trusted automatically.
- Token count, call count and time per agent are recorded in the event log from day 1.

## Models and providers

The project uses free model tiers only: no Claude API and no paid models, including as backups. The orchestrator and workers run on Gemini Flash-Lite's free tier, and the verifier runs on a different company's model, Qwen on Groq's free tier (DECISIONS 2026-10-25). That makes the check more independent than a model reviewing its own work.

| Role | Model (all free tiers) | Why |
| --- | --- | --- |
| Orchestrator + workers | Gemini Flash-Lite (`gemini-3.5-flash-lite`) | 10/10 on the week-1 model test; the only Gemini model whose free tier fits the workload (Flash: 20 requests/day) |
| Verifier | qwen3.8-27b on Groq | Different model family from the workers; 9/10 on the model test with no tool-calling slips |
| Verifier fallback | gpt-oss-120b on Groq, plus Cerebras (same model) for headroom | Groq caps it at 200k tokens/day |
| Overflow when a quota runs out | gpt-oss-20b on Groq, Cerebras free tier, OpenRouter `:free` models (50 requests/day) | Spreads load across providers; never a paid fallback |

- **Provider-neutral layer:** these providers expose OpenAI-compatible APIs. One small adapter (or LiteLLM) covers them, so switching models is a config change.
- **Week-1 model test:** run 10 questions on the free candidates and check tool calling, JSON output and SQL quality before committing.
- **Free-tier realities:** limits aren't guaranteed (Google publishes no exact free-tier numbers), models get retired (Groq retired its Llama models in Aug 2026), and 429 errors will happen. Plan for retries, backoff and a request queue.
- **When every free quota is used up:** the demo serves featured findings and cached answers only, and says when quotas reset. It never switches to a paid model.
- **Local models are out:** the development Mac (M1, 8 GB) can't run models strong enough for multi-step SQL.

## System architecture

Fixed rules go in code, judgment goes to the model. dbt removes duplicates, filters to city limits and drops impossible dates; agents map categories across cities and write the queries.

**Data layer** (offline, weekly)

- Ingest scripts per source type write dated raw Parquet files that are never modified.
- dbt-duckdb staging models clean lightly but keep each city's own category names; dbt tests check unique IDs, date ranges and monthly record counts.
- Two snapshots: a **frozen eval snapshot** (gold SQL runs on it, never changes) and a **live serving snapshot** (refreshed weekly).
- `registry.yaml` lists about 10 datasets with grain, date field and coverage. `quirks/<city>.md` notes are written from data exploration, before any eval question.
- A weekly GitHub Action archives San Antonio 311, keeping the latest version per Case ID.

**Backend** (FastAPI + Pydantic, async)

- Plain asyncio orchestration, no agent framework.
- Structured JSON output for the contract, worker results, verdict and answer.
- Agent tools: `describe_table`, `distinct_values`, `run_sql`, `get_population`.
- Read-only SQL sandbox: DuckDB read-only with external access off, sqlglot allows SELECT only, timeouts, 1,000-row cap.
- Every agent event saved to Postgres. SSE streams them live and resumes after disconnects.
- Answers cached by the metric contract's hash + snapshot version + prompt version.
- Per-IP rate limits and a daily quota guard.

**Frontend** (Next.js App Router + TypeScript)

- Server-rendered pages: `/`, `/q/[id]` (permalink with link previews), `/coverage`, `/methods`.
- Client components: question box, chips, live trace, Recharts charts drawn from the backend's chart spec.
- Tailwind + shadcn/ui; TanStack Query; types generated from FastAPI's OpenAPI schema.
- The browser connects to the API's SSE endpoint directly, not through Next.js.

**API**

| Endpoint | Purpose |
| --- | --- |
| `POST /api/questions` | Start a run (or return a cached answer) |
| `GET /api/questions/{id}/events` | SSE stream of agent events |
| `GET /api/questions/{id}` | Full answer (permalink) |
| `GET /api/questions/{id}.csv` | Answer data table |
| `GET /api/featured` | Precomputed findings |
| `GET /api/coverage` | Available topics × cities × years |

**Deployment and tooling**

| Tier | Includes |
| --- | --- |
| Must have (v1) | Vercel (frontend), Docker API on AWS App Runner/Fargate or Fly.io, managed Postgres (Neon/Supabase free), Sentry free, GitHub Actions CI with a 10-question eval smoke test, uv/Ruff/pyright, pnpm/ESLint/Vitest/Playwright |
| Week 7, if on track | Terraform, axe accessibility CI, link-preview images, feedback form |
| v2 | Langfuse tracing, job queue, follow-up questions, maps, animal shelter data |

Check App Runner's CPU behavior for background tasks before choosing it. Fargate or Fly.io keep the process running.

**Repo layout:** `apps/web` (Next.js), `apps/api` (FastAPI), `data/` (ingest, dbt, registry, quirks), `evals/` (questions, gold SQL, runners, results), `infra/`, `.github/workflows/`.

## UI and UX

The interface is a question box that returns a structured answer card, plus a front page of featured findings. It is not a chat thread, and it has no photos: the newspaper feel comes from typography (serif headlines, a clean grid, a dateline).

**Front page**

- Question box with guided chips (Topic · City · Measure · Years) and clickable example questions.
- 6–9 featured findings, precomputed. Each has gold SQL and a human check before publishing.
- A coverage grid (topics × cities, with years) showing first-time visitors what they can ask.

**While an answer runs**

- An honest time estimate and queue position appear at once, with the permalink, so people can leave and come back. Featured findings stay browsable while they wait.
- The "Interpreted as" bar appears as soon as the metric contract exists. The run pauses for confirmation only when the orchestrator flags ambiguity ("'noise' could include construction: include it?"); otherwise it continues, with an Adjust link that reruns with a new definition.
- A live agent trace (orchestrator, each city worker, verifier) stays open while running and collapses when the answer arrives. Screen readers hear only major steps through a polite live region: started, each city done, checked, answer ready.

**Answer card**

- One-sentence headline, the chart, the status, and a single always-visible caveat line.
- One Details area with tabs: Table · Method · Sources (dataset IDs, snapshot date, exact SQL).
- Status wording, each with an icon and a word, never color alone: "Recomputed by a second AI agent + N automated checks", "Figures disagree", "Partial", "Can't answer".
- Freshness line: "Data as of <snapshot date>".
- Permalink, CSV download, Copy citation, and "Report a wrong number" on a specific row or the headline.

**Chart by question type**

| Question type | Visual |
| --- | --- |
| Count | Big number + sentence |
| Trend over time | Line chart (2026 dashed, labeled year to date) |
| Ranking / top types | Horizontal bars |
| City comparison | Grouped bars or one line per city |
| Share | Bar or stacked bar, no pies |
| Time of day / seasonality | Columns by hour or month |
| Trap / unanswerable | Explanation card listing what is available |

**Rules:** one fixed color per city across the app, bars start at zero, raw counts on hover, a text summary for screen readers, phone layouts with tables scrolling inside their container and at most 4 chart series, WCAG 2.2 AA.

**Edge states**

- **Figures disagree:** both figures side by side, each with its definition and query, a plain explanation of the difference, and a choice of definition to rerun.
- **Daily free quota reached:** a designed screen offering featured findings, cached answers and the time quotas reset.
- **Chart spec fails validation:** show the headline and table, never a broken chart.
- **Every card** carries "AI-generated: check the method before publishing," linking to `/methods`, and the portal credits with the not-affiliated notice.

## Evaluation plan

Evaluation is the headline of the project. Every result runs on the frozen eval snapshot and is scored against gold answers from hand-written SQL that follows `definitions.md`; known reasonable alternative definitions are listed and accepted.

**Question set: 60 questions, split 40 development / 20 held-out test**

| Tier | Count | Example |
| --- | --- | --- |
| One city, one dataset | 20 | "How many Dallas 311 pothole requests in 2024?" |
| One city, several datasets | 15 | "Did Dallas shelter intake rise in the same months as stray-animal 311 calls?" |
| Cross-city comparison | 15 | "Which city had the largest rise in auto theft offenses, 2023–2025?" |
| Traps | 10 | Houston 311, Houston crime after June 2026, San Antonio 311 trends, impossible dates, ambiguous wording |

**Metrics**

- Answer accuracy within a stated tolerance.
- Definition correctness (the metric contract) against `definitions.md`, scored separately from numeric accuracy.
- Correct refusals on traps.
- Verifier catch rate on deliberately injected worker errors and wrong contracts.
- Verifier false-alarm rate: correct answers it wrongly flags.
- Consistency across 3 runs; model calls and time per question.

**Ablations**

1. A single agent with the same tools, registry, category catalogs and call budget.
2. Orchestrator + workers, no verifier.
3. The full system.
4. Verifier on the same model as the workers vs. a different model family.
5. Worker model comparison across free models: Gemini Flash-Lite vs. qwen3.8-27b vs. gpt-oss-120b (Gemini Flash only if its 20 requests/day allow).

General assistants (Gemini, ChatGPT) are scored on the test set only, for the "why can't Google do this?" comparison. Results are reported by question tier, since the multi-agent edge should show mainly on cross-city questions.

## Cost

Models cost $0: every model runs on a free tier, with no paid fallback. The only possible spending is hosting and an optional domain.

| Item | Cost |
| --- | --- |
| City data, Census | Free |
| LLM calls (Gemini, Groq, Cerebras, OpenRouter free tiers) | $0 |
| Frontend (Vercel Hobby), Postgres free tier, Sentry free, GitHub Actions | Free |
| Backend hosting | $0–25/month; AWS credits should cover App Runner or Fargate |
| Domain (optional) | ~$10–15/year |

**Keeping it within free limits**

- At 8–10 calls per question, the full eval (60 questions × 3 runs × 5 setups) is roughly 9,000 calls, more than a day's free quota. Spread runs across days and run setups in sequence.
- Measured 2026-10-25: Flash-Lite allows 500 requests/day, so 9,000 calls is 2–3 weeks of quota. Budget it: 1 run per question on dev, 3 runs only on the final test-split results, and drop setups that don't answer a question the write-up needs.
- Use 1 run per question during development; 3 runs only for final results.
- The full eval runs once per milestone, not weekly; CI runs the 10-question smoke test only.
- Demo protection: featured findings and cached answers make no model calls, per-IP limits apply, and the quota screen appears when free limits run out.

## Timeline

The build takes 7 weeks, with a measurable gate at the end of each week. Weeks 3–5 hold the core multi-agent work.

**7-week roadmap: one gate per week**

| Week | Phase | Goal | Done when |
| --- | --- | --- | --- |
| 1 | Data foundation | Snapshots, registry, definitions.md, quirks | Week-1 checks done; free model picked |
| 2 | Baseline | Single-agent baseline + first 30 gold questions | Baseline accuracy measured |
| 3 | Multi-agent | Metric contract + parallel city workers | First comparison vs. baseline |
| 4 | Verifier | Two-layer verifier; injected-error tests | Verifier catch rate measured |
| 5 | Full evaluation | All 60 questions, ablations, model comparison | Results table complete |
| 6 | Product UI | Answer card, Interpreted-as bar, chips | Ask, trace and answer work end to end |
| 7 | Launch | Permalinks, CSV, accessibility, deploy, README | **Public demo live** |

If a week slips, cut from the week-7 extras (Terraform, link-preview images, feedback form) before touching the evaluation.

## Risks and open checks

The two risks that matter most are wrong definitions and an untrustworthy eval. The verifier's contract review and the frozen snapshot address them.

| Risk | Mitigation |
| --- | --- |
| Wrong metric contract (e.g. which categories count as "noise") | Verifier reviews the contract before recomputing; `definitions.md`; confirmation when ambiguous; contract errors tracked as a metric |
| Free-tier rate limits make answers slow (1–2 minutes) | 8–10 calls per question; schema and categories in the prompt; load spread across free providers; queue; caching |
| Free-tier limits change or models disappear | Provider-neutral layer; overflow to other free providers; cached-only mode when all quotas are used; retries with backoff |
| Verifier weaker than the workers, raising false alarms | Measure false-alarm rate; code runs both queries and shows both figures |
| Personal data exposed in answers | Personal columns dropped in staging; ZIP/district minimum; cells below 5 hidden |
| Eval drift from weekly refreshes | Frozen eval snapshot, separate from the live one |
| Quirks notes leak eval answers | Write quirks from data exploration first; held-out questions test unlisted quirks |
| Portals change or block downloads (Houston already redirects) | Dated raw Parquet; manual downloads where needed |
| Multi-agent doesn't beat the baseline | Fair baseline; full category catalogs per worker; report results by tier; an honest negative result is still a finding |
| Too much infrastructure for one person | Stack tiers; Terraform and extras only in week 7 |

**Week-1 checks**

- [x] Write `definitions.md` and the comparable-offense mapping
- [x] Download Houston's 2023–2025 crime files manually and confirm coverage
- [x] Check coverage of Austin's NIBRS Group A dataset
- [x] Count records per month for every city × topic to find gaps
- [x] Check whether Dallas publishes NIBRS offense fields
- [x] Find the cause of Austin's 2023 311 jump
- [x] List the personal-data columns to drop in each dataset
- [x] Check whether Austin publishes usable animal shelter data
- [x] Recheck Houston 311 services
- [ ] Confirm free-tier limits in AI Studio, the Groq console and Cerebras (Gemini and Groq measured 2026-10-25: Flash-Lite 500 requests/day; Cerebras still open)
- [ ] Check App Runner background-CPU behavior and that AWS credits cover hosting
- [x] Run the 10-question test on the free candidate models (`docs/model_check/README.md`)

## Sources

- [Dallas OpenData](https://www.dallasopendata.com/) (311, police incidents, animal shelter)
- [Austin Open Data](https://datahub.austintexas.gov/) (311, crime reports)
- [Open Data San Antonio](https://data.sanantonio.gov/) (311 rolling 365 days, SAPD offenses)
- [HPD monthly NIBRS crime data](https://www.houstontx.gov/police/cs/Monthly_Crime_Data_by_Street_and_Police_Beat.htm)
- Related work: [PublicAgent](https://arxiv.org/html/2511.03023v1), [DataGovBench](https://huggingface.co/papers/2607.06482.md), [sodabar MCP](https://glama.ai/mcp/servers/UsmarHaider/sodabar), [local-dfw-mcp](https://glama.ai/mcp/servers/LizzleChen/local-dfw-mcp)
- Free LLM tiers: [Gemini free tier (Sept 2026 guide)](https://www.memetik.ai/guides/gemini-api-free-tier-limits), [free LLM APIs compared](https://openrouter.ai/blog/tutorials/free-llm-apis-compared/), [free tiers, Oct 2026](https://dev.to/tariqnasser/free-llm-api-tiers-in-october-2026-whats-left-and-how-i-chain-them-227l)
