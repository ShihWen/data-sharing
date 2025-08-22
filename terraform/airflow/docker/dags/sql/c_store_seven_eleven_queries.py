CHECK_NEW_DATA_QUERY = """
WITH bronze_dates AS (
    SELECT DISTINCT extract_date
    FROM `{project_id}.{bronze_dataset_id}`.seven_eleven
),
silver_dates AS (
    SELECT DISTINCT extract_date
    FROM `{project_id}.{silver_dataset_id}`.seven_eleven
),
new_date AS (
    SELECT bronze_dates.extract_date
    FROM bronze_dates
    LEFT JOIN silver_dates ON bronze_dates.extract_date = silver_dates.extract_date
    WHERE silver_dates.extract_date IS NULL
    ORDER BY bronze_dates.extract_date
    LIMIT 1  -- Only one date arrives at a time
)
SELECT 
    extract_date as new_date,
    CASE 
        WHEN extract_date IS NOT NULL THEN 'PROCESS_DATE'
        ELSE 'NO_NEW_DATA'
    END as action
FROM new_date
"""

TRANSFORM_AND_LOAD_DATE_QUERY = """
INSERT INTO `{project_id}.{silver_dataset_id}`.seven_eleven
(
    extract_date,
    store_id,
    store_name, 
    store_address,
)