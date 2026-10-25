# Dallas quirks

From exploration of the 2026-10-17 snapshots. Written before any eval question (CLAUDE.md rule 3).

## Police Incidents (`dallas_police`)

- **Several rows per offense.** One row per incident × offense line × person (`servnumid`). Count
  offenses as distinct `(incidentnum, nibrs_code)`.

  | Year | Rows | Incidents | Offenses |
  | --- | --- | --- | --- |
  | 2023 | 144,578 | 113,080 | 119,574 |
  | 2024 | 134,586 | 106,994 | 113,632 |
  | 2025 | 128,837 | 104,648 | 111,833 |

- That dedupe collapses multiple victims of the same offense into one. NIBRS counts person
  offenses per victim, so Dallas aggravated assault is likely low compared with Houston
  (`definitions.md`).
- **Includes Group B and non-NIBRS rows.** 2024 offenses (rows in brackets): 71.9k Group A
  (91.0k rows), 10.3k Group B (11.0k), 30.4k Group C, which is code `999`, non-NIBRS (31.6k),
  and 1.0k blank `nibrs_group`. The largest `nibrs_crime_category` is `MISCELLANEOUS`, and
  traffic violations are in the data too. "Total crime" uses `nibrs_group = 'A'` only.
- NIBRS fields are filled from 2017 on; 2014–2016 rows have them blank.
- `date1` is the occurrence start (`date1 <= reporteddate` in 99.995% of rows). Volume starts
  June 2014; the 690 rows dated 1967–2013 are back-dated occurrences and are dropped.
- Category labels: `nibrs_crime` is Dallas's own sub-label (`BURGLARY-RESIDENCE`, `UUMV` = motor
  vehicle theft, `ROBBERY-INDIVIDUAL`, …). Match on `nibrs_code`, never on labels.
- `city` is ~99.9% `DALLAS` (plus null, `DAL`, `DLS` and a few suburbs). It is not filtered;
  everything is DPD-reported.
- Personal columns include `mo` (free-text narrative with names and addresses) and officer
  names/badges; all are dropped in staging (registry).

## 311 (`dallas_311`)

- Starts 2020-10-01, so 2020 is a partial year (88k). Full years: 2021 411k, 2022 447k,
  2023 446k, 2024 471k, 2025 464k. No gaps or monthly outliers 2021–2026.
- **Type names carry a department suffix that changed in 2024.** Public Works (`PBW`) and
  Transportation (`TRN`) merged into `TPW`, so `Street Repair - Routine - PBW` becomes
  `Street Repair - Routine - TPW` partway through 2024. Other suffix changes: Homeless
  Encampment `OHS` → `ECR`/`EMCR` (2025), Dead Animal Pick Up gains `- SAN` (2025),
  Illegal Dumping Sign `CDS` → `CCS`. `definitions.md` lists all variants. Never filter by
  department.
- **`Code Concern - CCS` is a catch-all.** It has ~110–128k requests a year with no subtype,
  covering high weeds, junk, dumping and more. Dumping and similar code issues can't be separated
  in Dallas.
- Noise is only `Chronic Noise Complaint - DPD` (2.2k–3.7k a year); regular noise goes to police
  non-emergency.
- No pothole-only type; street repair types are used instead.
- `Sanitation Same Day Missed Collection - SAN` exists only in 2021, and `Animal Loose Cat - DAS`
  only in 2021 (folded into `Animal Loose - DAS`).
- `service_request_number` and `unique_key` are unique.
- 3 requests have no `service_request_type` (2024–2026). They are kept and count only toward
  totals.

## Animal shelter (`dallas_shelter`)

- One row per intake (impound); `impound_number` is unique (125,563 rows).
  `activity_number` is shared by many rows.
- An animal can enter many times: 2025 has 41.0k intakes for 32.4k animals. `FOSTER` (7.2k in
  2025) and `TREATMENT` (1.3k) intakes are mostly animals returning to the system.
- Fiscal-year file: starts 2023-10-01 (2023 = Oct–Dec only, 8.8k).
- Impossible future dates: one row each in 2027, 2029, 2030 and 2920; drop them. Staging also
  drops rows with an `outcome_date` after the snapshot (8 rows dropped in all).
- 8 rows have an `outcome_date` before their `intake_date`, 3 of them before the file starts
  (2022-12-27, 2023-02-04, 1969-10-19). They are kept; they fall outside any 2023-10+ outcome
  window.
- Animal types: DOG 76k, CAT 39k, BIRD 7k, WILDLIFE 2.8k, LIVESTOCK 107.
- `source_id` (owner/finder person id), `staff_id`, `receipt_number`, `additional_information`
  and `census_tract` are dropped in staging.
