"""
SQL queries for MRT traffic FULL LOAD data processing.
These queries are used by the mrt_traffic_bronze_to_silver_full_load DAG.
Designed for one-time historical data backfill with optimized batch processing.
"""

# Query to check current state and prerequisites for full load
CHECK_PREREQUISITES_QUERY = """
WITH bronze_stats AS (
    SELECT 
        COUNT(*) as total_records,
        COUNT(DISTINCT DATE_TRUNC(dt, MONTH)) as total_months,
        MIN(dt) as min_date,
        MAX(dt) as max_date
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_bronze_dataset_id }}.mrt_traffic`
),
silver_stats AS (
    SELECT 
        COUNT(*) as total_records,
        COUNT(DISTINCT DATE_TRUNC(dt, MONTH)) as total_months,
        MIN(dt) as min_date,
        MAX(dt) as max_date
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_traffic`
)
SELECT 
    bronze_stats.total_records as bronze_records,
    bronze_stats.total_months as bronze_months,
    bronze_stats.min_date as bronze_min_date,
    bronze_stats.max_date as bronze_max_date,
    silver_stats.total_records as silver_records,
    silver_stats.total_months as silver_months,
    CASE 
        WHEN silver_stats.total_records = 0 THEN 'EMPTY_SILVER_TABLE'
        WHEN bronze_stats.total_months > silver_stats.total_months THEN 'PARTIAL_LOAD_NEEDED'
        WHEN bronze_stats.total_records = silver_stats.total_records THEN 'ALREADY_COMPLETE'
        ELSE 'NEEDS_VERIFICATION'
    END as load_status
FROM bronze_stats, silver_stats
"""

# Full load processing query - processes data year by year for optimal performance
FULL_LOAD_YEAR_BATCH_QUERY = """
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
    WHERE EXTRACT(YEAR FROM dt) = {{ params.target_year }}
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
SELECT * FROM new_records
ORDER BY dt, hour, entrance, exit
"""

# Validation query to compare bronze vs silver after full load completion
FULL_LOAD_VALIDATION_QUERY = """
WITH comparison AS (
    SELECT 
        'bronze' as source,
        COUNT(*) as record_count,
        COUNT(DISTINCT DATE_TRUNC(dt, MONTH)) as unique_months,
        COUNT(DISTINCT EXTRACT(YEAR FROM dt)) as unique_years,
        MIN(dt) as min_date,
        MAX(dt) as max_date
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_bronze_dataset_id }}.mrt_traffic`
    
    UNION ALL
    
    SELECT 
        'silver' as source,
        COUNT(*) as record_count,
        COUNT(DISTINCT DATE_TRUNC(dt, MONTH)) as unique_months,
        COUNT(DISTINCT EXTRACT(YEAR FROM dt)) as unique_years,
        MIN(dt) as min_date,
        MAX(dt) as max_date
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_traffic`
),
with_percentages AS (
    SELECT 
        *,
        CASE 
            WHEN source = 'silver' THEN 
                ROUND((record_count * 100.0) / LAG(record_count) OVER (ORDER BY source), 2)
            ELSE NULL
        END as completion_percentage
    FROM comparison
)
SELECT * FROM with_percentages
ORDER BY source
"""

# Cost estimation query - helps estimate processing costs before execution
COST_ESTIMATION_QUERY = """
WITH bronze_analysis AS (
    SELECT 
        EXTRACT(YEAR FROM dt) as year,
        COUNT(*) as records_per_year,
        COUNT(DISTINCT DATE_TRUNC(dt, MONTH)) as months_per_year,
        MIN(dt) as year_start,
        MAX(dt) as year_end
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_bronze_dataset_id }}.mrt_traffic`
    GROUP BY EXTRACT(YEAR FROM dt)
),
size_estimates AS (
    SELECT 
        year,
        records_per_year,
        months_per_year,
        -- Estimate data size (assuming ~42 bytes per record average)
        ROUND((records_per_year * 42) / (1024*1024*1024), 2) as estimated_gb_per_year,
        year_start,
        year_end
    FROM bronze_analysis
)
SELECT 
    year,
    records_per_year,
    months_per_year,
    estimated_gb_per_year,
    year_start,
    year_end,
    -- Cost estimation (approximate)
    ROUND(estimated_gb_per_year * 0.02, 2) as estimated_processing_cost_usd,
    ROUND(estimated_gb_per_year * 0.005, 3) as estimated_storage_cost_monthly_usd
FROM size_estimates
ORDER BY year
""" 