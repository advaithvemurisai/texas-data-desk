-- One row per offense line. Count offenses with sum(offense_count), never count(*).
-- Headers were renamed from the 2025 file on and dates are M/D/YYYY through 2025, ISO in
-- 2026; both are handled here. The blank last row of each 2019-2024 file is dropped.
-- Dropped: street number/name/type/suffix, coordinates, beat (both header eras).
with unified as (
    select
        Incident as incident,
        coalesce(RMSOccurrenceDate, "Occurrence Date") as occurrence_date_raw,
        coalesce(RMSOccurrenceHour, "Occurrence Hour") as occurrence_hour_raw,
        coalesce(NIBRSClass, "NIBRS Class") as nibrs_class,
        coalesce(NIBRSDescription, "NIBRS Description") as nibrs_description,
        coalesce(OffenseCount, "Offense Count") as offense_count_raw,
        Premise as premise,
        City as city,
        coalesce(ZIPCode, "ZIP Code") as zip_code,
        source_file
    from {{ source('raw', 'houston_nibrs') }}
)

select
    incident,
    coalesce(
        try_strptime(occurrence_date_raw, '%m/%d/%Y'),
        try_strptime(occurrence_date_raw, '%Y-%m-%d')
    )::date as occurred_date,
    try_cast(occurrence_hour_raw as integer) as occurred_hour,
    nibrs_class,
    nibrs_description,
    cast(offense_count_raw as integer) as offense_count,
    premise,
    city,
    zip_code,
    source_file
from unified
where incident is not null
