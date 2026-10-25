-- One row per NIBRS offense: distinct (incidentnum, nibrs_code). The raw table has one row
-- per incident x offense line x person (servnumid), ~1.26 rows per incident (CLAUDE.md rule 4).
-- nibrs_code is blank before 2017 and on some non-NIBRS rows; those stay one offense per
-- incident, matching the counts in data/quirks/dallas.md.
-- Dropped: names, badges, demographics, narrative (mo), address, coordinates, beat, ra, taag.
-- Rows dated before 2014-06-01 are back-dated occurrences and are dropped.
with rows as (
    select
        *,
        {{ to_timestamp('date1') }} as occurred_at
    from {{ source('raw', 'dallas_police') }}
)

select
    incidentnum || '|' || coalesce(nibrs_code, '') as offense_key,
    incidentnum,
    nibrs_code,
    -- nibrs_group and the dates are the same on every row of an offense; the labels and
    -- places can differ on a few catch-all codes (999, 90Z), so a fixed pick is taken.
    min(nibrs_group) as nibrs_group,
    min(nibrs_crime) as nibrs_crime,
    min(nibrs_crime_category) as nibrs_crime_category,
    min(nibrs_crimeagainst) as nibrs_crimeagainst,
    min(occurred_at) as occurred_at,
    cast(min(occurred_at) as date) as occurred_date,
    min({{ to_timestamp('reporteddate') }}) as reported_at,
    min(premise) as premise,
    min(division) as division,
    min({{ council_district('district', 14) }}) as council_district,
    min(zip_code) as zip_code,
    min(city) as city,
    min(status) as status,
    count(*) as source_rows
from rows
where occurred_at >= date '2014-06-01'
  and cast(occurred_at as date) <= {{ snapshot_date('dallas_police') }}
group by incidentnum, nibrs_code
