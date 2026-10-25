# Decisions

Why key choices were made. Don't reverse any of these without a new entry explaining what changed.

## 2026-10-17 · Free model tiers only
**Decision:** every model runs on a free tier: Gemini Flash for the orchestrator and workers, gpt-oss-120b on Groq for the verifier, and other free tiers for overflow. No Claude API and no paid models, not even as a backup.
**Why:** the project must cost $0 in model spend and stay runnable as a public demo. Having a paid fallback would quietly become the default the first time a quota runs out.
**Consequences:** 429s and changing limits are expected, so we need retries, backoff, a queue and a provider-neutral adapter. When all quotas are used, the app serves cached and featured answers only. The eval runs are spread across days.

## 2026-10-17 · Fort Worth excluded
**Decision:** v1 covers Houston, San Antonio, Dallas and Austin only.
**Why:** Fort Worth's portal has 10 datasets and none has been updated since July 2025. That isn't enough data, or recent enough, for the topics and years we compare.
**Revisit if:** the portal resumes regular updates and publishes 311 and NIBRS crime data.

## 2026-10-17 · San Antonio 311 is a rolling window
**Decision:** no San Antonio 311 trend or multi-year questions. SA 311 only answers last-12-months questions. 311 trends (2021–2025) are Dallas and Austin only. A weekly GitHub Action archives SA 311 from week 1 onward.
**Why:** the CKAN dataset holds only the "past 365 days of the last upload" (2024 = 940 rows, 2026 = 407k). Year counts from it would be artifacts of the window, not real changes.
**Consequences:** asking for "San Antonio 311 trends" is a trap question; the correct behavior is to decline and say what is available instead. Our own weekly archive may support trends later, but only from the date it started.

## 2026-10-17 · Crime counted in NIBRS offenses
**Decision:** the crime unit is offenses (the NIBRS standard), not incidents and not rows. Austin uses NIBRS Group A Offense Crimes (`i7fg-wrk5`), not the older Crime Reports dataset. Houston sums `Offense Count`. Dallas dedupes at incident + offense level. Cross-city comparisons use only the comparable-offense list in `definitions.md`.
**Why:** each city publishes crime at a different grain. Dallas has ~1.26 rows per incident; Houston rows carry a count field. NIBRS offenses are the only unit that all four cities can be mapped to consistently, and they match how Houston and San Antonio already publish.
**Consequences:** counting incidents or raw rows is wrong for this project, even when it is simpler. Gold SQL and the verifier both follow the offense rule.

## 2026-10-18 · San Antonio crime is dated by report date
**Decision:** San Antonio offenses are dated by `Report_Date`, the only date SAPD publishes. Every other city uses occurrence date. Answers that include San Antonio crime say so.
**Why:** the data behaves like a report date: no rows before the 2023-01-01 window start, and no spike on the 1st of the month (3.23% of rows, the same as Austin's report date; Austin's occurrence date is 4.25%). Dropping San Antonio from crime comparisons would cost one of four cities for a small effect. In Austin, which has both dates, yearly totals by report vs occurrence date differ by ≤1.1% for 2023–2025.
**Consequences:** this is an exception to "crime is dated by occurrence date" (CLAUDE.md rule 4). Monthly and day-of-week questions for San Antonio describe when offenses were reported, not when they happened. Evidence is in `data/quirks/san_antonio.md`.

## 2026-10-18 · "Total crime" means NIBRS Group A
**Decision:** any all-offense total ("total crime", "all offenses") counts NIBRS Group A only. Dallas filters `nibrs_group = 'A'`; Houston drops classes `90A`–`90Z`.
**Why:** Austin and San Antonio publish only Group A, while Dallas and Houston also include Group B (DUI, trespass, disorderly conduct, …; ~11k Dallas and ~35k Houston offenses in 2024). Mixed totals would inflate Dallas and Houston.
**Consequences:** Dallas has no NIBRS total before 2017 (NIBRS fields are blank 2014–2016). Cross-city comparisons still use only the comparable-offense list in `data/definitions.md`.

## 2026-10-18 · Austin shelter data not used; shelter stays Dallas-only
**Decision:** v1 does not use Austin Animal Center data.
**Why:** it is split at a system change on 2025-05-05 (ShelterBuddy). The legacy and new datasets use different intake categories, and the new one adds ~4.3k "Community Animal - Program" intakes, so there is no consistent series across that date. Only ~17 months exist after the switch.
**Revisit if:** v2 adds shelter questions limited to post-May-2025 data (the new datasets refresh hourly), or the city publishes a crosswalk between the two systems.

## 2026-10-24 · Eval snapshot frozen
**Decision:** the eval environment in `data/snapshots.yaml` is pinned to the 2026-10-17 snapshots, except San Antonio 311, which uses 2026-10-18. Gold SQL runs only on `data/warehouse_eval.duckdb`, built from these.
**Why:** these are the snapshots `definitions.md` and the quirks notes were written from. The 2026-10-18 San Antonio 311 pull is the one that was explored, and its window (2025-10-17 … 2026-10-16) lines up with the other cities' snapshot dates. A dbt test (`frozen_snapshot_counts`) checks that staging on this snapshot reproduces the quirks counts.
**Consequences:** the eval data ends at different dates per city: Austin and San Antonio crime 2026-09-30, Houston 2026-06-30, Dallas and the 311 data mid-October 2026. Changing any eval date needs a new entry here, and every gold answer must be recomputed.

## 2026-10-24 · Dallas police staged at offense grain only
**Decision:** dbt exposes Dallas police only as `stg_dallas_police_offenses`, one row per distinct `(incidentnum, nibrs_code)`. The person-level raw rows are not staged.
**Why:** agents would otherwise count raw rows (~1.26 per incident), which breaks CLAUDE.md rule 4. Offenses with a blank `nibrs_code` stay one offense per incident, which matches the quirks counts.
**Consequences:** person-level fields (victim type, involvement) are not available to agents. Labels that differ between rows of the same offense (`nibrs_crime_category` on catch-all codes 999/90Z, `premise`) take a fixed pick (`min`). `nibrs_type` is not staged because it disagrees between rows of the same offense.

## 2026-10-25 · Flash-Lite for the agents, Qwen on Groq for the verifier
**Decision:** the orchestrator and workers use `gemini-3.5-flash-lite`. The verifier uses `qwen/qwen3.8-27b` on Groq, with `openai/gpt-oss-120b` (Groq, plus Cerebras, which serves the same model) as its fallback. All free tiers. This replaces the model choice in the 2026-10-17 free-tiers entry; the free-tiers-only rule itself is unchanged.
**Why:** the week-1 model test (`docs/model_check/README.md`) measured the free tiers. Gemini Flash (3.5 and 3.8) allows only 20 requests a day, about two questions. Flash-Lite answered 10/10 and was never rate-limited. Qwen answered 9/10 with no tool-calling slips. gpt-oss-120b answered in plain text instead of calling tools 29 times in 9 questions and hit Groq's 200k-tokens-a-day limit. No model returned a wrong number.
**Consequences:** the verifier is still a different model family from the workers. Groq rejects any single request above its per-minute token limit (Qwen: 7k input, 1k output), so verifier prompts must stay small and see one city's notes at a time. The test was one run of 10 questions: a screen, not a benchmark. The week-5 model comparison re-checks the choice on the dev set. Flash-Lite's free tier (AI Studio, 2026-10-25) is 15 requests/minute, 250k tokens/minute and 500 requests/day: about 50 questions a day at 8–10 calls each, so the full eval has to be budgeted in days (see PLAN, cost section).

## 2026-10-25 · API hosted on Vercel Hobby, next to the frontend
**Decision:** the FastAPI backend runs as a Python function on Vercel's free Hobby plan, in the same project as the Next.js frontend, with the DuckDB warehouse bundled into the function. Each question runs inside one streamed request. Fallback if a limit bites: Google Cloud Run, in its own Google Cloud project (never the Gemini project, whose free tier depends on billing being off).
**Why:** the plan assumed AWS App Runner, but App Runner no longer accepts new customers, and new AWS accounts get $100–200 of credits on a free plan that closes after 6 months, too short for a lasting public demo. Free Docker hosting has also shrunk: Hugging Face Docker Spaces now need a paid plan, Fly.io has no free tier for new accounts, and Render and Koyeb free instances have 512 MB of RAM and 0.1 vCPU, too little for a 329 MB warehouse. Vercel Hobby (checked 2026-10-25) is free with no card. It gives functions 2 GB of memory, 1 vCPU, 300 s per request and a 500 MB uncompressed bundle for Python (the API needs about 400 MB). When monthly usage runs out, functions pause; they are never billed. Waiting on model calls does not count as active CPU, so free model quotas run out long before Vercel's do.
**Consequences:** one question, including retries and backoff, must finish within 300 s, or stop with a partial answer that says why. No background workers: the orchestrator runs inside the request and streams the trace. Cached answers and featured findings live in Postgres (Neon free), not on the function's disk. The warehouse ships with each deploy, so a weekly data refresh means a redeploy. Hobby is limited to non-commercial personal use, which fits a portfolio demo. If the bundle outgrows 500 MB, Vercel's large-functions beta (up to 5 GB) comes next, then Cloud Run.
**Update 2026-10-25, first deploy:** two limits were tighter than the docs suggested. Uploads reject any file over 100 MB, so the warehouse ships as one zstd Parquet file per staging table (221 MB in total, largest 86 MB) instead of a 329 MB `.duckdb` file, exposed as views with only that folder readable. And the code-plus-data bundle is capped at 225 MB, so the project runs on the large-functions beta (`VERCEL_SUPPORT_LARGE_FUNCTIONS=1`). Measured: cold start 2.0 s, warm requests 0.3–1.0 s. Watch: Dallas 311 grows toward the 100 MB file limit (split it by year when it gets close; the staging script refuses files over 95 MB), and the large-functions beta could change.
