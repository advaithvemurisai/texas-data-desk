{# Text timestamp to TIMESTAMP. Socrata uses 2024-01-31T13:05:00.000, Dallas police has
   7 fractional digits (2024-01-31 13:05:00.0000000); seconds precision is all we need. #}
{% macro to_timestamp(column) -%}
  try_cast(replace(left({{ column }}, 19), 'T', ' ') as timestamp)
{%- endmacro %}


{# A single council district 1..max_district as an integer; anything else (blank, 0,
   multi-district lists like '2,14', stray codes) becomes null. Dallas police writes D7. #}
{% macro council_district(column, max_district) -%}
  case
    when regexp_matches(trim({{ column }}), '^D?[0-9]{1,2}$')
     and cast(ltrim(trim({{ column }}), 'D') as integer) between 1 and {{ max_district }}
    then cast(ltrim(trim({{ column }}), 'D') as integer)
  end
{%- endmacro %}
