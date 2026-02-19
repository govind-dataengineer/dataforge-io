{{ config(
    materialized='view',
    tags=['bronze', 'orders']
) }}

SELECT
  *
FROM delta.`{{ var("bronze_path") }}/orders/`
WHERE _dataforge_ingestion_timestamp >= CURRENT_DATE - INTERVAL 30 DAY
