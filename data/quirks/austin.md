# Austin quirks

From exploration of the 2026-10-17 snapshots. Written before any eval question (CLAUDE.md rule 3).

## 311 (`austin_311`)

- **The 2023 jump (204k → 354k, +73%) is mostly not real demand.** Requests by year:
  2020 158.5k, 2021 181.6k, 2022 204.4k, 2023 354.2k, 2024 290.0k, 2025 298.9k.
  The causes:
  1. **February 2023 ice storm.** `ARR - Storm Debris Collection` had 39,180 requests in Feb 2023
     and 47,266 in 2023 (0 in 2024). Feb 2023 alone is 63.3k requests, 2.8× a normal month.
  2. **Police noise calls moved into 311.** `APD - Non Emergency Noise/Alarm` started
     2022-09-11: 7 in 2022, 21.3k in 2023, 28.7k in 2024. APD's 311 volume went from
     359 (2021) to 41.4k (2023).
  3. **New request types.** Austin Resource Recovery split its types in 2022 (`ARR - Garbage`,
     `ARR - Recycling`, `ARR - Compost` start April 2022). `ACD - Request Code Officer` ran
     2022-04 … 2023-12 (14.5k in 2023). The 311 Command Center's own types start in 2022
     (10.1k in 2023).
  - Rule: Austin 311 totals are not compared across 2022/2023. Category trends are fine where
    the type list in `definitions.md` spans the change.
- **Low base in late 2021 – early 2022.** Monthly totals are ~9.4k–10.5k (Nov 2021 – Feb 2022),
  under half today's median. This is before the new types arrived, not a gap.
- **Renamed request types.** The same request changes name over time; `definitions.md` lists all
  the names.
  - `Pothole Repair` (≤2023) → `SBO - Pothole Repair` (2023–24) → `TPW - Pothole Repair` (2024–)
  - `Loose Dog` (≤2023) → `Animal Protection - Loose Dog` (2023–); the same applies to most
    animal types.
  - `Austin Code - Request Code Officer` → `ACD - …` → `DSD - Request Code Officer` (2023–)
  - Prefixes `ZZ`/`ZZZ`/`Zz_` mark retired types that still hold old rows.
  - One type has an HTML entity: `SBO - Alley &amp; Unpaved Street Maintenance` (2024).
- **Renamed departments.** Transportation and Public Works merged into
  `Transportation and Public Works` (2024–; Transportation 0 in 2025). Austin Code Department
  moved under Development Services (`Austin Code Department` 440 in 2024, 0 in 2025). Never
  filter by department.
- **Intake method:** `Web` stops in 2025 (1 row). Phone and Spot311 carry almost all requests.
- **`sr_location_city` is messy:** mostly `AUSTIN`, plus nulls (1.1k in 2024) and other cities
  (`PFLUGERVILLE`, `MANOR`, `LAKEWAY`, …; a few hundred each). Normalize casing. City-wide
  counts keep all rows (requests handled by City of Austin 311); answers "in Austin" do not
  filter by this field.
- `sr_number` is unique. Snapshot ends 2026-10-16.

## NIBRS Group A Offense Crimes (`austin_nibrs`)

- Coverage 2019-01-01 … 2026-09-30, 580,302 rows, `offenseid` unique (one row per offense).
  `primary_key` is the incident number.
- Has both `occurred_date` (use this) and `reported_date`. Yearly totals differ by ≤1.1%
  (2023: 72,685 vs 73,190), and the median report lag is 0 days.
- The NIBRS code is the first 3 characters of `nibrs_desc` (`240 Motor Vehicle Theft`).
  `nibrs_category` is "Crimes Against Persons/Property/Society". Robbery is under Property, as
  in NIBRS.
- `nibrs_offense_code_and_extension_description` is Austin's own finer label (e.g.
  `BURGLARY OF RESIDENCE`, `AGG ROBBERY/DEADLY WEAPON`). It is fine for single-city detail and
  never used to match across cities.
- Group A only; no Group B offenses are published.
- Occurrence dates spike on the 1st of the month (4.25% of 2024 rows vs ~3.3% expected): an
  unknown day defaults to the 1st. Day-level questions on the 1st are unreliable.

## Animal shelter: not used

- Austin Animal Center data is split at a system change on **2025-05-05** (ShelterBuddy launch):
  - Legacy `wter-evkm` (intakes) / `9t4d-g238` (outcomes): 2013-10-01 … 2025-05-04, frozen.
  - New `pyqf-r2dc` (intakes) / `gsvs-ypi7` (outcomes): 2025-05-04 onward, hourly.
- The intake categories don't match. Legacy uses `intake_type` (Stray, Owner Surrender, Public
  Assist, …). New uses `source_name` (Stray, ACO - Impound, Community Animal - Program, Returns,
  …). The new system adds ~4.3k "Community Animal - Program" intakes and splits Cat/Kitten and
  Dog/Puppy.
- New intakes ran ~13k a year vs ~11.8k in legacy 2024, so a single series would show a break.
  The new data also carries names and found addresses.
- Excluded from v1; shelter stays Dallas-only (DECISIONS 2026-10-18).
