# San Antonio quirks

From exploration of the 2026-10-17 (offenses) and 2026-10-18 (311) snapshots. Written before any
eval question (CLAUDE.md rule 3).

## SAPD Offenses (`sa_offenses`)

- **`Report_Date` is a report date, not an occurrence date.** The portal gives no definition (the
  "Data Preparation - Offenses" PDF only lists filters). The data shows it:
  - No back-dated tail: the earliest row is exactly 2023-01-01. Occurrence-dated data always has
    old occurrences reported late (e.g. Dallas has 690 rows dated 1967–2013).
  - No spike on the 1st of the month: 3.23% of 2024 rows, the same as Austin's `reported_date`
    (3.18%) and the uniform rate (~3.3%). Austin's `occurred_date` spikes to 4.25%, because an
    unknown day defaults to the 1st.
  - Effect on yearly counts is small. In Austin, which has both dates, yearly totals by report
    vs occurrence date differ by ≤1.1% for 2023–2025 (median lag 0 days, p90 13–17 days).
  - Rule: SA crime is dated by `Report_Date`, and every answer including SA crime says so
    (DECISIONS 2026-10-18).
- `DateTime` is the extract date (one value per file, e.g. 2026-10-01), not an event time.
- Coverage: 2023-01-01 … 2026-09-30 (549,314 rows). Yearly: 2023 159.6k, 2024 153.9k,
  2025 136.7k.
- Group A only, SAPD jurisdiction only, "Not Reportable to NIBRS" removed (portal prep notes).
- No NIBRS code column. Offenses are identified by `NIBRS_Code_Name`; group by `NIBRS_Group`;
  `NIBRS_Crime_Against` is PERSON / PROPERTY / SOCIETY.
- `Report_ID` + `NIBRS_Code_Name` is unique in all but 27 rows; one row = one offense.
- `Zip_Code` has a value "Out of Jurisdiction" for zips outside SAPD's area.
- No personal or sub-ZIP columns.

## 311 Service Calls (`sa_311`)

- **Rolling window.** The file covers "the past 365 days of the last upload". The window is in
  the file: `Report Starting Date` … `Report Ending Date` (2026-10-18 snapshot:
  2025-10-17 … 2026-10-16). No trends or year-over-year (DECISIONS 2026-10-17).
- **Rows outside the window.** 14,622 of 509,935 rows (2.9%) were opened before the window start,
  as far back as 2020-10-28. They are still-open or recently touched old cases. Filter
  `OPENEDDATETIME >= "Report Starting Date"` for "last 12 months".
- The first month of the window is partial (2025-10 has 16.9k vs a ~42k median).
- Type hierarchy: `Category` (broad) > `TYPENAME` (specific); `REASONNAME` and `Dept` are
  department routing.
- No noise category and no homeless-related category beyond `Homeless Encampment` /
  `Encampment Abatement`.
- `CASEID` is unique. `OBJECTDESC` is a street address and `XCOORD`/`YCOORD` are coordinates;
  all three are dropped in staging.
- Our weekly archive (GitHub release `sa311-archive`) starts 2026-10-17. Trends from it are only
  possible from that date on.
