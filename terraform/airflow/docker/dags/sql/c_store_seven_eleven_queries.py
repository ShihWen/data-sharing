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
    LEFT JOIN silver_dates ON bronze_dates.extract_date = format_date('%Y-%m-%d', silver_dates.extract_date)
    WHERE silver_dates.extract_date IS NULL
    and bronze_dates.extract_date not like '%/%/%'
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

CHECK_DUPLICATE_STORE_QUERY = """
SELECT name, city
FROM `{project_id}.{bronze_dataset_id}`.seven_eleven
WHERE name is not null
and extract_date = '{target_date}'
GROUP BY name, city
HAVING COUNT(*) > 1
"""

PROCESS_DUPLICATE_STORE_STEP1_LIST_DUPLICATE_STORES = """
CREATE OR REPLACE TABLE `{project_id}.{silver_dataset_id}.seven_eleven_step1_duplicate_{{{{ ds_nodash }}}}` AS
SELECT *
       , CURRENT_TIMESTAMP() AS processed_at
FROM `{project_id}.{bronze_dataset_id}`.seven_eleven
WHERE extract_date = '{target_date}';
"""

PROCESS_DUPLICATE_STORE_STEP2_REMOVE_EXACT_DUPLICATE_STORES = """
CREATE OR REPLACE TABLE `{project_id}.{silver_dataset_id}.seven_eleven_step2_remove_exact_duplicate_{{{{ ds_nodash }}}}` AS
SELECT distinct extract_date
            , name
            , city
            , district
            , address
            , long
            , lat
            , service 
            , CURRENT_TIMESTAMP() AS processed_at
FROM `{project_id}.{silver_dataset_id}.seven_eleven_step1_duplicate_{{{{ ds_nodash }}}}`
WHERE extract_date = '{target_date}';
"""

