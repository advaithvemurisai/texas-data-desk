{# Stop a run whose --vars and --target name different environments, so an eval build can
   never read live snapshots or write into the live warehouse (and the other way round). #}
{% macro check_snapshot_env() %}
  {% if execute %}
    {% set env = var('snapshot_env') %}
    {% if env == 'unset' or not var('snapshots') %}
      {{ exceptions.raise_compiler_error(
          'No snapshots given. Pass --vars "$(uv run tdd-ingest dbt-vars ' ~ target.name ~ ')"') }}
    {% endif %}
    {% if env != target.name %}
      {{ exceptions.raise_compiler_error(
          'vars are for "' ~ env ~ '" but --target is "' ~ target.name ~ '"') }}
    {% endif %}
  {% endif %}
  select 1
{% endmacro %}


{# The raw snapshot date this run reads for a dataset, as a SQL date literal. Rows dated
   after it are impossible (data-entry errors) and staging drops them. #}
{% macro snapshot_date(dataset_id) %}
  {%- set day = var('snapshots').get(dataset_id) -%}
  {%- if execute and not day -%}
    {{ exceptions.raise_compiler_error('no snapshot date for ' ~ dataset_id) }}
  {%- endif -%}
  date '{{ day }}'
{%- endmacro %}
