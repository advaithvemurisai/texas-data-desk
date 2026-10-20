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
