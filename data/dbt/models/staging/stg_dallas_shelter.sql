-- One row per intake (impound_number is unique; an animal can have many intakes).
-- Dropped: source_id, staff_id, receipt_number, additional_information, census_tract.
-- Rows with an intake or outcome date after the snapshot (2027, 2029, 2030, 2920) are
-- data-entry errors and are dropped.
with typed as (
    select
        impound_number,
        animal_id,
        animal_type,
        animal_breed,
        kennel_number,
        kennel_status,
        tag_type,
        activity_number,
        cast(activity_sequence as integer) as activity_sequence,
        {{ council_district('council_district', 14) }} as council_district,
        intake_type,
        intake_subtype,
        cast(intake_total as integer) as intake_total,
        reason,
        cast({{ to_timestamp('intake_date') }} as date) as intake_date,
        try_cast(intake_time as time) as intake_time,
        cast({{ to_timestamp('due_out') }} as date) as due_out,
        intake_condition,
        hold_request,
        outcome_type,
        outcome_subtype,
        cast({{ to_timestamp('outcome_date') }} as date) as outcome_date,
        try_cast(outcome_time as time) as outcome_time,
        outcome_condition,
        service_request_number,
        chip_status,
        animal_origin,
        month as month_label,
        year as fiscal_year_label
    from {{ source('raw', 'dallas_shelter') }}
)

select *
from typed
where intake_date <= {{ snapshot_date('dallas_shelter') }}
  and (outcome_date is null or outcome_date <= {{ snapshot_date('dallas_shelter') }})
