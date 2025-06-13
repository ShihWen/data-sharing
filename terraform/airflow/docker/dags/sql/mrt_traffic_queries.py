"""
SQL queries for MRT traffic data processing.
These queries are used by the mrt_traffic_bronze_to_silver_weekly DAG.
"""

CHECK_NEW_DATA_QUERY = """
WITH bronze_count AS (
    SELECT COUNT(*) as count
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_bronze_dataset_id }}.mrt_traffic_bronze`
),
silver_count AS (
    SELECT COUNT(*) as count
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_traffic_silver`
)
SELECT 
    CASE 
        WHEN bronze_count.count > silver_count.count THEN true
        ELSE false
    END as has_new_data
FROM bronze_count, silver_count
"""

TRANSFORM_AND_LOAD_QUERY = """
INSERT INTO `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_traffic_silver`
(
    dt,
    hour,
    entrance,
    exit,
    traffic,
    is_valid_traffic,
    day_of_week,
    day_type,
    peak_period,
    processed_at
)
SELECT
    dt,
    hour,
    entrance,
    exit,
    traffic,
    -- Basic validation: traffic should be non-negative
    traffic >= 0 as is_valid_traffic,
    -- Extract day of week (1 = Monday, 7 = Sunday)
    EXTRACT(DAYOFWEEK FROM dt) as day_of_week,
    -- Determine if it's a weekday or weekend
    CASE 
        WHEN EXTRACT(DAYOFWEEK FROM dt) IN (1, 7) THEN 'weekend'
        ELSE 'weekday'
    END as day_type,
    -- Determine peak period
    CASE 
        WHEN hour BETWEEN 7 AND 9 THEN 'morning_peak'
        WHEN hour BETWEEN 17 AND 19 THEN 'evening_peak'
        ELSE 'off_peak'
    END as peak_period,
    CURRENT_TIMESTAMP() as processed_at
FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_bronze_dataset_id }}.mrt_traffic_bronze`
WHERE dt >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)  -- Process last 30 days of data
""" 