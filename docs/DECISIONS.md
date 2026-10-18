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
