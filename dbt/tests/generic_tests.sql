-- Custom dbt tests for DataForge

{% test positive_values(model, column_name) %}
  SELECT *
  FROM {{ model }}
  WHERE {{ column_name }} < 0
{% endtest %}

{% test valid_email(model, column_name) %}
  SELECT *
  FROM {{ model }}
  WHERE NOT {{ column_name }} LIKE '%@%.%'
{% endtest %}
