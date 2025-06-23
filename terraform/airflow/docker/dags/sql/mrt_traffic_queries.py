"""
SQL queries for MRT traffic data processing - SIMPLIFIED VERSION.
These queries are used by the mrt_traffic_bronze_to_silver_weekly DAG.
Since only one month arrives at a time, we removed all complex batching logic.
"""

# Simple check: Is there a new month in bronze that's not in silver?
CHECK_NEW_MONTH_QUERY = """
WITH bronze_months AS (
    SELECT DISTINCT DATE_TRUNC(dt, MONTH) as month
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_bronze_dataset_id }}.mrt_traffic`
),
silver_months AS (
    SELECT DISTINCT DATE_TRUNC(dt, MONTH) as month  
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_traffic`
),
new_month AS (
    SELECT bronze_months.month
    FROM bronze_months
    LEFT JOIN silver_months ON bronze_months.month = silver_months.month
    WHERE silver_months.month IS NULL
    ORDER BY bronze_months.month
    LIMIT 1  -- Only one month arrives at a time
)
SELECT 
    month as new_month,
    CASE 
        WHEN month IS NOT NULL THEN 'PROCESS_MONTH'
        ELSE 'NO_NEW_DATA'
    END as action
FROM new_month
"""

# Simple transform and load for the new month
TRANSFORM_AND_LOAD_MONTH_QUERY = """
INSERT INTO `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_traffic`
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
    -- Clean up known exit name inconsistencies
    CASE 
        WHEN exit = 'G大坪林' THEN '大坪林'
        WHEN exit = 'O景安' THEN '景安'
        WHEN exit = 'O頭前庄' THEN '頭前庄'
        ELSE exit 
    END as exit,
    traffic,
    -- Basic validation: traffic should be non-negative
    traffic >= 0 as is_valid_traffic,
    -- Extract day of week (1 = Sunday, 2 = Monday, ..., 7 = Saturday)
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
FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_bronze_dataset_id }}.mrt_traffic`
WHERE DATE_TRUNC(dt, MONTH) = DATE('{{ params.target_month }}')
"""

# Simple validation query
VALIDATE_PROCESSING_QUERY = """
WITH processing_stats AS (
    SELECT 
        COUNT(*) as records_processed,
        MIN(dt) as min_date,
        MAX(dt) as max_date,
        COUNT(CASE WHEN is_valid_traffic = false THEN 1 END) as invalid_records,
        COUNT(DISTINCT dt) as unique_dates
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_traffic`
    WHERE processed_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
)
SELECT 
    *,
    CASE 
        WHEN records_processed > 0 THEN 'SUCCESS'
        ELSE 'NO_RECORDS_PROCESSED'
    END as status,
    ROUND((invalid_records * 100.0) / NULLIF(records_processed, 0), 2) as invalid_percentage
FROM processing_stats
"""

# Legacy queries (kept for compatibility if needed)
CHECK_PROCESSING_STRATEGY_QUERY = CHECK_NEW_MONTH_QUERY
TRANSFORM_AND_LOAD_INCREMENTAL_QUERY = TRANSFORM_AND_LOAD_MONTH_QUERY
CHECK_NEW_DATA_QUERY = CHECK_NEW_MONTH_QUERY
TRANSFORM_AND_LOAD_QUERY = TRANSFORM_AND_LOAD_MONTH_QUERY
GET_NEXT_BATCH_QUERY = CHECK_NEW_MONTH_QUERY
GET_MISSING_MONTHS_QUERY = CHECK_NEW_MONTH_QUERY

# Station name validation query
VALIDATE_STATION_NAMES_QUERY = r"""
-- This query checks for inconsistencies between station exit and entrance names
-- in the bronze layer. It helps identify stations that don't have a matching
-- entrance for an exit, which could indicate data entry errors.

SELECT
    A.exit,
    B.entrance
FROM (
    SELECT DISTINCT exit
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_bronze_dataset_id }}.mrt_traffic`
) AS A
FULL JOIN (
    SELECT DISTINCT entrance
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_bronze_dataset_id }}.mrt_traffic`
) AS B
    ON A.exit = B.entrance
WHERE
    A.exit IS NULL OR B.entrance IS NULL;
""" 