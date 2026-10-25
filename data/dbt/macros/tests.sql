{# Every non-null value lies in [min_date, max_date]; max_date defaults to the snapshot date. #}
{% test date_between(model, column_name, dataset_id, min_date, max_date=none) %}
  select {{ column_name }}
  from {{ model }}
  where cast({{ column_name }} as date) < date '{{ min_date }}'
     or cast({{ column_name }} as date) > {{ "date '" ~ max_date ~ "'" if max_date else snapshot_date(dataset_id) }}
{% endtest %}


{# Every calendar month from start through end has at least min_rows rows: catches gaps
   and truncated pulls. Returns the months that fall short. #}
{% test monthly_rows_at_least(model, column_name, start, end, min_rows) %}
  with months as (
    select unnest(generate_series(date '{{ start }}', date '{{ end }}', interval 1 month)) as month
  ),
  counts as (
    select date_trunc('month', {{ column_name }}) as month, count(*) as n
    from {{ model }}
    group by 1
  )
  select months.month, coalesce(counts.n, 0) as n
  from months
  left join counts using (month)
  where coalesce(counts.n, 0) < {{ min_rows }}
{% endtest %}
