-- One row per offense (offenseid is unique). Group A only. Dropped: victim gender, age
-- range and race/ethnicity, census block group.
select
    trim(offenseid) as offense_id,
    primary_key as incident_number,
    left(nibrs_desc, 3) as nibrs_code,
    nibrs_desc,
    nibrs_category,
    nibrs_group,
    nibrs_offense_code_and_extension_description,
    cast({{ to_timestamp('occurred_date') }} as date) as occurred_date,
    occurred_on_time,
    cast({{ to_timestamp('reported_date') }} as date) as reported_date,
    occurred_day_of_week,
    sector,
    {{ council_district('council_district', 10) }} as council_district,
    zip_code,
    location_description,
    internal_clearance_status
from {{ source('raw', 'austin_nibrs') }}
