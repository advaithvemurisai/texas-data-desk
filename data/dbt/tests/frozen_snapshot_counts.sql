-- The frozen eval snapshot must reproduce the counts in data/quirks/<city>.md, which were
-- measured on it by hand. A failure means staging changed how something is counted.
-- Live snapshots move, so this runs on the eval target only.
{{ config(enabled = target.name == 'eval') }}

with actual as (
    select 'dallas offenses 2023' as check_name, count(*) as n
    from {{ ref('stg_dallas_police_offenses') }} where year(occurred_date) = 2023
    union all
    select 'dallas offenses 2024', count(*)
    from {{ ref('stg_dallas_police_offenses') }} where year(occurred_date) = 2024
    union all
    select 'dallas offenses 2025', count(*)
    from {{ ref('stg_dallas_police_offenses') }} where year(occurred_date) = 2025
    union all
    select 'houston aggravated assault 2023-2025', sum(offense_count)
    from {{ ref('stg_houston_nibrs') }}
    where nibrs_class = '13A' and year(occurred_date) between 2023 and 2025
    union all
    select 'austin offenses 2023', count(*)
    from {{ ref('stg_austin_nibrs') }} where year(occurred_date) = 2023
    union all
    select 'austin 311 2023', count(*)
    from {{ ref('stg_austin_311') }} where year(created_at) = 2023
    union all
    select 'sa 311 in window', count(*)
    from {{ ref('stg_sa_311') }}
    union all
    select 'dallas shelter intakes', count(*)
    from {{ ref('stg_dallas_shelter') }}
),

expected (check_name, n) as (
    values
        ('dallas offenses 2023', 119574),
        ('dallas offenses 2024', 113632),
        ('dallas offenses 2025', 111833),
        ('houston aggravated assault 2023-2025', 50851),
        ('austin offenses 2023', 72685),
        ('austin 311 2023', 354187),
        ('sa 311 in window', 509935 - 14622),
        ('dallas shelter intakes', 125563 - 8)  -- 4 future intakes, 4 future outcomes
)

select expected.check_name, expected.n as expected, actual.n as actual
from expected
left join actual using (check_name)
where actual.n is distinct from expected.n
