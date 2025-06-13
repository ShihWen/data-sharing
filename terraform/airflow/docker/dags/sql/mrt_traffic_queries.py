"""
SQL queries for MRT traffic data processing.
These queries are used by the mrt_traffic_bronze_to_silver_weekly DAG.
Updated to use month-based processing logic for monthly data updates.
"""

# Check if it's first run and determine processing strategy (month-based)
CHECK_PROCESSING_STRATEGY_QUERY = """
WITH silver_stats AS (
    SELECT 
        COUNT(*) as record_count,
        COALESCE(MIN(DATE_TRUNC(dt, MONTH)), CURRENT_DATE()) as min_month,
        COALESCE(MAX(DATE_TRUNC(dt, MONTH)), CURRENT_DATE()) as max_month
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_traffic`
),
bronze_stats AS (
    SELECT 
        COUNT(*) as record_count,
        MIN(DATE_TRUNC(dt, MONTH)) as min_month,
        MAX(DATE_TRUNC(dt, MONTH)) as max_month
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_bronze_dataset_id }}.mrt_traffic`
),
month_comparison AS (
    SELECT 
        bronze_stats.record_count as bronze_count,
        silver_stats.record_count as silver_count,
        bronze_stats.record_count - silver_stats.record_count as records_diff,
        -- Count distinct months in each layer
        (SELECT COUNT(DISTINCT DATE_TRUNC(dt, MONTH)) 
         FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_bronze_dataset_id }}.mrt_traffic`) as bronze_months,
        (SELECT COUNT(DISTINCT DATE_TRUNC(dt, MONTH)) 
         FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_traffic`) as silver_months,
        bronze_stats.min_month as bronze_min_month,
        bronze_stats.max_month as bronze_max_month,
        silver_stats.max_month as silver_max_month
    FROM bronze_stats, silver_stats
),
processing_config AS (
    SELECT 
        *,
        CASE 
            WHEN silver_count = 0 THEN 'FIRST_RUN'
            WHEN bronze_months > silver_months THEN 'INCREMENTAL'
            ELSE 'NO_NEW_DATA'
        END as run_type
    FROM month_comparison
)
SELECT 
    *,
    -- For first run, determine batch start month (process in 6-month chunks)
    CASE 
        WHEN run_type = 'FIRST_RUN' THEN bronze_min_month
        WHEN run_type = 'INCREMENTAL' THEN 
            COALESCE(DATE_ADD(silver_max_month, INTERVAL 1 MONTH), bronze_min_month)
        ELSE NULL
    END as batch_start_month,
    CASE 
        WHEN run_type = 'FIRST_RUN' THEN 
            LEAST(
                DATE_ADD(bronze_min_month, INTERVAL 6 MONTH),
                bronze_max_month
            )
        WHEN run_type = 'INCREMENTAL' THEN bronze_max_month
        ELSE NULL
    END as batch_end_month,
    -- Determine if we need more batches after this one for first run
    CASE 
        WHEN run_type = 'FIRST_RUN' AND DATE_ADD(bronze_min_month, INTERVAL 6 MONTH) < bronze_max_month THEN true
        ELSE false
    END as has_more_batches,
    -- Calculate months to process
    CASE 
        WHEN run_type = 'INCREMENTAL' THEN bronze_months - silver_months
        WHEN run_type = 'FIRST_RUN' THEN 
            DATE_DIFF(
                LEAST(DATE_ADD(bronze_min_month, INTERVAL 6 MONTH), bronze_max_month),
                bronze_min_month,
                MONTH
            ) + 1
        ELSE 0
    END as months_to_process
FROM processing_config
"""

# Legacy query for backward compatibility (now deprecated)
CHECK_NEW_DATA_QUERY = """
WITH bronze_count AS (
    SELECT COUNT(*) as count
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_bronze_dataset_id }}.mrt_traffic`
),
silver_count AS (
    SELECT COUNT(*) as count
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_traffic`
)
SELECT 
    CASE 
        WHEN bronze_count.count > silver_count.count THEN true
        ELSE false
    END as has_new_data
FROM bronze_count, silver_count
"""

# Enhanced transform and load query with month-based incremental logic
TRANSFORM_AND_LOAD_INCREMENTAL_QUERY = """
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
WITH bronze_data AS (
    SELECT
        dt,
        hour,
        entrance,
        exit,
        traffic,
        -- Basic validation: traffic should be non-negative
        traffic >= 0 as is_valid_traffic,
        -- Extract day of week (1 = Sunday, 2 = Monday, ..., 7 = Saturday in BigQuery)
        EXTRACT(DAYOFWEEK FROM dt) as day_of_week_num,
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
    WHERE DATE_TRUNC(dt, MONTH) BETWEEN DATE('{{ params.start_month }}') AND DATE('{{ params.end_month }}')
),
new_records AS (
    SELECT bronze_data.*
    FROM bronze_data
    WHERE NOT EXISTS (
        SELECT 1 
        FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_traffic` silver
        WHERE silver.dt = bronze_data.dt 
        AND silver.hour = bronze_data.hour
        AND silver.entrance = bronze_data.entrance  
        AND silver.exit = bronze_data.exit
    )
)
SELECT 
    dt,
    hour,
    entrance,
    exit,
    traffic,
    is_valid_traffic,
    day_of_week_num as day_of_week,
    day_type,
    peak_period,
    processed_at
FROM new_records
ORDER BY dt, hour, entrance, exit
"""

# Legacy query (now uses date filtering instead of hard-coded 30 days)
TRANSFORM_AND_LOAD_QUERY = """
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
    exit,
    traffic,
    -- Basic validation: traffic should be non-negative
    traffic >= 0 as is_valid_traffic,
    -- Extract day of week (1 = Sunday, 2 = Monday, ..., 7 = Saturday in BigQuery)
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
WHERE dt >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)  -- Process last 30 days of data
"""

# Query to get the next batch month range for first run processing
GET_NEXT_BATCH_QUERY = """
WITH silver_progress AS (
    SELECT 
        MAX(DATE_TRUNC(dt, MONTH)) as last_processed_month
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_traffic`
),
bronze_range AS (
    SELECT 
        MIN(DATE_TRUNC(dt, MONTH)) as min_month,
        MAX(DATE_TRUNC(dt, MONTH)) as max_month
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_bronze_dataset_id }}.mrt_traffic`
)
SELECT 
    COALESCE(DATE_ADD(silver_progress.last_processed_month, INTERVAL 1 MONTH), bronze_range.min_month) as batch_start_month,
    LEAST(
        COALESCE(DATE_ADD(silver_progress.last_processed_month, INTERVAL 6 MONTH), DATE_ADD(bronze_range.min_month, INTERVAL 6 MONTH)),
        bronze_range.max_month
    ) as batch_end_month,
    bronze_range.max_month as bronze_max_month,
    CASE 
        WHEN COALESCE(DATE_ADD(silver_progress.last_processed_month, INTERVAL 6 MONTH), DATE_ADD(bronze_range.min_month, INTERVAL 6 MONTH)) < bronze_range.max_month 
        THEN true
        ELSE false
    END as has_more_batches,
    -- Calculate number of months in this batch
    DATE_DIFF(
        LEAST(
            COALESCE(DATE_ADD(silver_progress.last_processed_month, INTERVAL 6 MONTH), DATE_ADD(bronze_range.min_month, INTERVAL 6 MONTH)),
            bronze_range.max_month
        ),
        COALESCE(DATE_ADD(silver_progress.last_processed_month, INTERVAL 1 MONTH), bronze_range.min_month),
        MONTH
    ) + 1 as months_in_batch
FROM silver_progress, bronze_range
"""

# Query to get missing months for incremental processing
GET_MISSING_MONTHS_QUERY = """
WITH bronze_months AS (
    SELECT DISTINCT DATE_TRUNC(dt, MONTH) as month
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_bronze_dataset_id }}.mrt_traffic`
),
silver_months AS (
    SELECT DISTINCT DATE_TRUNC(dt, MONTH) as month
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_traffic`
),
missing_months AS (
    SELECT bronze_months.month
    FROM bronze_months
    LEFT JOIN silver_months ON bronze_months.month = silver_months.month
    WHERE silver_months.month IS NULL
    ORDER BY bronze_months.month
)
SELECT 
    MIN(month) as start_month,
    MAX(month) as end_month,
    COUNT(*) as missing_month_count,
    ARRAY_AGG(month ORDER BY month) as missing_months_list
FROM missing_months
"""

# Query to validate the processing results (month-aware)
VALIDATE_PROCESSING_QUERY = """
WITH processing_stats AS (
    SELECT 
        COUNT(*) as records_processed,
        MIN(dt) as min_date_processed,
        MAX(dt) as max_date_processed,
        COUNT(CASE WHEN is_valid_traffic = false THEN 1 END) as invalid_records,
        COUNT(DISTINCT dt) as unique_dates_processed,
        COUNT(DISTINCT DATE_TRUNC(dt, MONTH)) as unique_months_processed
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_traffic`
    WHERE processed_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR)
),
month_summary AS (
    SELECT 
        DATE_TRUNC(dt, MONTH) as month,
        COUNT(*) as records_in_month,
        COUNT(DISTINCT dt) as days_in_month,
        AVG(traffic) as avg_traffic_in_month
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_traffic`
    WHERE processed_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR)
    GROUP BY DATE_TRUNC(dt, MONTH)
    ORDER BY month
)
SELECT 
    processing_stats.*,
    CASE 
        WHEN processing_stats.records_processed > 0 THEN 'SUCCESS'
        ELSE 'NO_RECORDS_PROCESSED'
    END as processing_status,
    ROUND((processing_stats.invalid_records * 100.0) / NULLIF(processing_stats.records_processed, 0), 2) as invalid_record_percentage,
    ARRAY_AGG(STRUCT(month_summary.month, month_summary.records_in_month, month_summary.days_in_month, month_summary.avg_traffic_in_month) ORDER BY month_summary.month) as monthly_summary
FROM processing_stats, month_summary
GROUP BY processing_stats.records_processed, processing_stats.min_date_processed, processing_stats.max_date_processed, 
         processing_stats.invalid_records, processing_stats.unique_dates_processed, processing_stats.unique_months_processed
""" 