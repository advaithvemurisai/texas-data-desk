-- One row per case, last 12 months only. The source is a rolling 365-day window
-- (report_start_date .. report_end_date, in the file); the ~3% of cases opened before the
-- window start are old still-open cases and are dropped. Dropped: OBJECTDESC (address),
-- XCOORD, YCOORD. CLOSEDDATETIME 1900-01-01 is a placeholder and becomes null.
with typed as (
    select
        CASEID as case_id,
        {{ to_timestamp('OPENEDDATETIME') }} as opened_at,
        {{ to_timestamp('CLOSEDDATETIME') }} as closed_raw,
        {{ to_timestamp('SLA_Date') }} as sla_due_at,
        "Late (Yes/No)" = 'YES' as is_late,
        Dept as dept,
        REASONNAME as reason_name,
        TYPENAME as type_name,
        Category as category,
        CategoryKey as category_key,
        CASESTATUS as case_status,
        SOURCEID as intake_source,  -- channel (web, phone, ...), not a person
        {{ council_district('COUNCIL_DIST', 10) }} as council_district,
        cast("Report Starting Date" as date) as report_start_date,
        cast("Report Ending Date" as date) as report_end_date
    from {{ source('raw', 'sa_311') }}
)

select
    * exclude (closed_raw),
    case when closed_raw >= timestamp '2000-01-01' then closed_raw end as closed_at
from typed
where opened_at >= report_start_date
