{{ config(
    materialized='table',
    tags=['silver', 'orders'],
    partition_by='order_date'
) }}

WITH source AS (
  SELECT * FROM {{ ref('stg_orders') }}
),

cleaned AS (
  SELECT
    order_id,
    customer_id,
    order_date,
    CAST(order_amount AS DECIMAL(18, 2)) as order_amount,
    order_status,
    lower(trim(payment_method)) as payment_method,
    CURRENT_TIMESTAMP as dbt_loaded_at
  FROM source
  WHERE order_id IS NOT NULL
    AND customer_id IS NOT NULL
    AND order_amount >= 0
)

SELECT * FROM cleaned
