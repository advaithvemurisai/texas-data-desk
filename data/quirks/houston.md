# Houston quirks

From exploration of the 2026-10-17 snapshot. Written before any eval question (CLAUDE.md rule 3).

## HPD NIBRS yearly files (`houston_nibrs`)

- **Sum `Offense Count`; never count rows.** Most rows are 1, but 2023–2025 has 16.4k rows with 2,
  2.3k with 3 and up to larger values, plus 92 rows with 0. Aggravated assault 2023–2025: 42,951
  rows vs 50,851 offenses (counted per victim, as in NIBRS).
- **Headers changed in the 2025 file.** `RMSOccurrenceDate` → `Occurrence Date`, `OffenseCount` →
  `Offense Count`, `NIBRSClass` → `NIBRS Class`, `NIBRSDescription` → `NIBRS Description`,
  `ZIPCode` → `ZIP Code`, and the street fields. Read with `union_by_name` and coalesce.
- **Date format changed in the 2026 file.** 2019–2025 use `M/D/YYYY` (`1/1/2023`); 2026 uses ISO
  `YYYY-MM-DD`. Parse both.
- Each 2019–2024 file ends with one blank row (all columns null); drop it.
- Each yearly file holds exactly that year's occurrences (no cross-year rows).
- Offenses by year: 2019 268.7k, 2020 260.4k, 2021 259.5k, 2022 265.6k, 2023 264.7k,
  2024 258.8k, 2025 248.3k, 2026 (Jan–Jun) 102.7k.
- **2026 ends 2026-06-30.** 2026 appears only as Jan–Jun equal-period comparisons.
- **Includes Group B.** Classes `90A`–`90Z` (DUI, trespass, disorderly conduct, all other
  offenses, …; ~35k offenses in 2024). Exclude them for "total crime" (`definitions.md`).
- `City` is mostly `HOUSTON`, with some `HARRIS CO`, `PEARLAND`, `SOUTH HOUSTON`, etc. (~1%).
  These are HPD-reported offenses; they are not filtered.
- Street number/name/type/suffix, coordinates and `Beat` are dropped in staging.
- Downloads from houstontx.gov worked directly on 2026-10-17. `data/manual/houston/` is the
  fallback if the site blocks again.

## 311: not available

- Rechecked 2026-10-18. The ArcGIS service
  `mycity2.houstontx.gov/.../311/Houston311_RecentServiceRequests` returns
  `500 "Service ... not started"`. data.houstontx.gov only has static 2023 files (BARC animal
  requests, Lagan knowledge dump).
- Houston 311 stays out of scope; asking for it is a trap question (decline, say what is
  available).
