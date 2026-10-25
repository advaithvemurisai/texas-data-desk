-- One row per offense. Group A only. reported_date is a REPORT date, the only date SAPD
-- publishes (DECISIONS 2026-10-18). There is no NIBRS code column; match on nibrs_code_name.
-- zip_code also holds 'Out of Jurisdiction' and 'Not Listed'. No personal columns.
select
    Report_ID as report_id,
    cast(Report_Date as date) as reported_date,
    NIBRS_Code_Name as nibrs_code_name,
    NIBRS_Group as nibrs_group,
    NIBRS_Crime_Against as nibrs_crime_against,
    Service_Area as service_area,
    Zip_Code as zip_code,
    cast("DateTime" as date) as extract_date
from {{ source('raw', 'sa_offenses') }}
