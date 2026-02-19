{{ config(
    materialized='table',
    tags=['gold', 'analytics', 'orders']
) }}

WITH orders AS (
  SELECT * FROM {{ ref('fct_orders') }}
),

daily_summary AS (
  SELECT
    order_date,
    COUNT(DISTINCT order_id) as total_orders,
    COUNT(DISTINCT customer_id) as unique_customers,
    SUM(order_amount) as total_revenue,
    AVG(order_amount) as avg_order_value,
    MIN(order_amount) as min_order_value,
    MAX(order_amount) as max_order_value,
    CURRENT_TIMESTAMP as created_at
  FROM orders
  GROUP BY order_date
)

SELECT * FROM daily_summary
ORDER BY order_date DESC
