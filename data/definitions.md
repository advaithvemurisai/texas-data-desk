# Definitions

Canonical meaning of each concept the desk can be asked about, per city. The orchestrator's
metric contract, the workers, the verifier and gold SQL all follow this file.

Written 2026-10-18 from data exploration of the 2026-10-17 snapshots (SA 311: 2026-10-18),
before any eval question existed. Do not edit it to make an eval question pass (CLAUDE.md
rule 3). City-specific traps are in `data/quirks/<city>.md`.

## Crime

### Unit and date

- Unit: NIBRS offenses (DECISIONS 2026-10-17).
  - Dallas: one offense = distinct `(incidentnum, nibrs_code)`.
  - Austin: one row = one offense (`offenseid` is unique).
  - San Antonio: one row = one offense.
  - Houston: sum `Offense Count` (`OffenseCount` before 2025); never count rows.
- Date: occurrence date. **Exception:** San Antonio publishes only a report date
  (`Report_Date`); see DECISIONS 2026-10-18. Answers that include San Antonio crime say so.

| City | Date column | Offense code column |
| --- | --- | --- |
| Dallas | `date1` | `nibrs_code` |
| Austin | `occurred_date` | first 3 characters of `nibrs_desc` (e.g. `240 Motor Vehicle Theft`) |
| San Antonio | `Report_Date` (report date) | none; match on `NIBRS_Code_Name` |
| Houston | `RMSOccurrenceDate` / `Occurrence Date` | `NIBRSClass` / `NIBRS Class` |

### Comparable offenses (cross-city)

Only these may be compared across cities. Each is a single NIBRS code.

| Offense | NIBRS | Dallas `nibrs_code` | Austin code | San Antonio `NIBRS_Code_Name` | Houston class |
| --- | --- | --- | --- | --- | --- |
| Homicide (murder & non-negligent manslaughter) | 09A | `09A` | `09A` | `Murder & Nonnegligent Manslaughter` | `09A` |
| Robbery | 120 | `120` | `120` | `Robbery` | `120` |
| Aggravated assault | 13A | `13A` | `13A` | `Aggravated Assault` | `13A` |
| Burglary / breaking & entering | 220 | `220` | `220` | `Burglary/Breaking & Entering` | `220` |
| Motor vehicle theft | 240 | `240` | `240` | `Motor Vehicle Theft` | `240` |

- Homicide is 09A only. Negligent manslaughter (09B) and justifiable homicide (09C, not a
  crime) are excluded everywhere. San Antonio does not publish 09C at all.
- Homicide counts are small (hundreds a year per city). The small-numbers rule applies: no
  % change on fewer than 50 records.
- Dallas codes `SHOPLIFT CONTACT` as 120, so it counts as robbery, the same as in NIBRS.
- Known limitation, aggravated assault: NIBRS counts crimes against persons once per victim.
  Houston's `Offense Count` does this (2023–2025: 42,951 rows, 50,851 offenses). The Dallas
  dedupe on `(incidentnum, nibrs_code)` collapses multiple victims into one offense, so Dallas
  13A is likely undercounted relative to Houston. Answers comparing aggravated assault across
  cities say so.

### "Total crime" / "all offenses"

NIBRS Group A only. Austin and San Antonio publish Group A only, so Group B rows are dropped
elsewhere:

- Dallas: `nibrs_group = 'A'` (2024: 91.0k Group A, 11.0k Group B, 1.0k blank).
- Houston: exclude classes starting `90` (Group B: DUI, trespass, disorderly conduct, …;
  ~35k offenses in 2024).
- Dallas rows dated before 2017 have no NIBRS fields; there is no Dallas NIBRS total before 2017.

Other single-city categories (e.g. larceny, vandalism, drug offenses) may be answered within one
city using that city's own NIBRS code or group, but are not compared across cities in v1.

## 311 service requests

### Unit and date

- Unit: service requests (one row each; ids are unique in all three cities).
- Date: creation date: Dallas `created_date`, Austin `sr_created_date`, San Antonio
  `OPENEDDATETIME`.
- Concepts are defined by exact request-type names because departments were renamed mid-series in
  both Dallas and Austin (see quirks). Never filter 311 by department.
- San Antonio is last-12-months only. Its window is `Report Starting Date` … `Report Ending
  Date` (in the file). Rows opened before the window start are dropped.

### Concepts

A blank cell means the city has no request type for that concept. Answer "not published",
not zero.

**Potholes / street repair**
- Dallas (street repair, not pothole-only): `Street Repair - Routine - PBW`,
  `Street Repair - Routine - TPW`, `Alley/Sidewalk/Street Repair - Hazardous - PBW`,
  `Alley/Sidewalk/Street Repair - Hazardous - TPW`
- Austin (potholes): `Pothole Repair`, `SBO - Pothole Repair`, `TPW - Pothole Repair`
- San Antonio (potholes): `Pavement Repair (Pothole)`
- Dallas has no pothole-only type. A pothole comparison involving Dallas says it is comparing
  street repair with potholes.

**Noise**
- Dallas: `Chronic Noise Complaint - DPD`. This is chronic noise only; one-off noise goes to
  police non-emergency, not 311.
- Austin: `APD - Non Emergency Noise/Alarm`, `Loud Commercial Music`,
  `Zz_Loud Commercial Music`, `DSD - Outdoor Commercial Venue Music Complaint`
- San Antonio: (none)
- Austin noise is not comparable across 2022/2023: APD noise calls enter 311 from Sept 2022
  (7 in 2022, 21,321 in 2023). Austin noise trends start in 2023.
- Dallas and Austin noise measure different things and are not compared.

**Graffiti**
- Dallas (public infrastructure only): `Graffiti City Streets & Bridges - PBW`,
  `Graffiti City Streets & Bridges - TPW`, `Graffiti Traffic Sign - TRN`,
  `Graffiti Traffic Sign - TPW`, `Graffiti Traffic Signal - TRN`,
  `Graffiti Traffic Signal - TPW`
- Austin: `Public Health - Graffiti Abatement`, `APH - Graffiti Abatement - Public Property`,
  `DSD - Graffiti Abatement - Private Property`,
  `ZZ DSD - Graffiti Abatement - Private Property`
- San Antonio: every type in `Category = 'Graffiti'`
- Austin private-property graffiti only starts in 2025.

**Loose / stray animals**
- Dallas: `Animal Loose - DAS`, `Animal Loose Cat - DAS` (2021 only; merged into Animal Loose)
- Austin: `Loose Dog`, `Loose Animal Not Dog`, `Animal Protection - Loose Dog`,
  `Animal Protection - Loose Animal Not Dog`
- San Antonio: `Animals(Stray Animal)`

**Dead animal pickup**
- Dallas: `Dead Animal Pick Up - DAS`, `Dead Animal Pick Up - SAN` (from 2025)
- Austin: `ARR Dead Animal Collection`, `ARR - Dead Animal Collection`,
  `ZZZ ARR Dead Animal Collection`
- San Antonio: `Dead Animal Pick Up`

**Homeless encampments**
- Dallas: `Homeless Encampment - OHS`, `Homeless Encampment - ECR`,
  `Homeless Encampment - EMCR`
- Austin: (none)
- San Antonio: `Homeless Encampment`, `Encampment Abatement`

**Street lights**
- Dallas: `Street Lighting - Maintenance- TRN`, `Street Lighting - Maintenance- TPW`
- Austin: `Street Light Issue- Address`,
  `Street Light Issue- Multiple poles/multiple streets`, `AE Street Light Issue - Address`,
  `AE Street Light Issue - No Address`
- San Antonio: (not checked; treat as not published)

**Illegal dumping**
- Dallas: (none usable). Dumping reports fall inside the catch-all `Code Concern - CCS`
  (~110–128k a year, no subtype); the `Illegal Dumping Sign/Urgent` types are tiny and specific.
- Austin: (none)
- San Antonio: `Illegal Dumping`
- San Antonio only, last 12 months.

Any other concept: the orchestrator asks the user to confirm the exact request types before
answering, and the verifier checks that list against this file's rules.

## Animal shelter (Dallas only)

- Unit: one intake = one row (`impound_number` is unique). Date: `intake_date`.
- "Intakes" = all rows. "New arrivals" excludes animals coming back into the system
  (`intake_type IN ('FOSTER', 'TREATMENT')`); answers say which one was used.
- Outcomes are counted on `outcome_date` using `outcome_type` (e.g. `ADOPTION`, `EUTHANIZED`,
  `RETURNED TO OWNER`, `TRANSFER`).
- Coverage: fiscal years 2023–2026 (from 2023-10-01). Rows dated after the snapshot (2027,
  2029, 2030, 2920) are data-entry errors and are dropped.
- Austin shelter data is not used (DECISIONS 2026-10-18).
