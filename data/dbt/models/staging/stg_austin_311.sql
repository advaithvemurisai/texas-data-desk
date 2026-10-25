-- One row per service request. Dropped: street address, street number/name, coordinates,
-- map page/tile (registry pii_columns). Request type names are kept exactly as published;
-- data/definitions.md matches on them.
select
    sr_number,
    sr_type_desc,
    sr_department_desc,
    sr_method_received_desc,
    sr_status_desc,
    {{ to_timestamp('sr_created_date') }} as created_at,
    {{ to_timestamp('sr_updated_date') }} as updated_at,
    {{ to_timestamp('sr_status_date') }} as status_at,
    {{ to_timestamp('sr_closed_date') }} as closed_at,
    upper(trim(sr_location_city)) as location_city,  -- not a filter for "in Austin" (quirks)
    sr_location_zip_code as zip_code,
    sr_location_county as county,
    {{ council_district('sr_location_council_district', 10) }} as council_district
from {{ source('raw', 'austin_311') }}
