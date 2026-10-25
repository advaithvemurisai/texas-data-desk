-- One row per service request. Dropped: address, lat_location (registry pii_columns).
select
    service_request_number,
    unique_key,
    service_request_type,
    department,
    {{ council_district('city_council_district', 14) }} as council_district,
    city_council_district as council_district_raw,  -- keeps multi-district lists like '2,14'
    status,
    priority,
    method_received_description,
    outcome,
    ert_estimated_response_time,
    {{ to_timestamp('created_date') }} as created_at,
    {{ to_timestamp('update_date') }} as updated_at,
    {{ to_timestamp('closed_date') }} as closed_at,
    {{ to_timestamp('overall_service_request_due_date') }} as due_at
from {{ source('raw', 'dallas_311') }}
