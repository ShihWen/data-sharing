CHECK_NEW_DATA_QUERY = """
WITH bronze_dates AS (
    SELECT DISTINCT extract_date
    FROM `{project_id}.{bronze_dataset_id}`.family_mart
),
silver_dates AS (
    SELECT DISTINCT extract_date
    FROM `{project_id}.{silver_dataset_id}`.family_mart
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
FROM `{project_id}.{bronze_dataset_id}`.family_mart
WHERE name is not null
and extract_date = '{target_date}'
GROUP BY name, city
HAVING COUNT(*) > 1
"""

INSERT_NO_DUPLICATE_DATA_TO_SILVER_QUERY = """
INSERT INTO `{project_id}.{silver_dataset_id}.family_mart`
SELECT PARSE_DATE('%Y-%m-%d', extract_date) as extract_date
       , name
       , city
       , district
       , address
       , ST_GEOGPOINT(long, lat) as location
       , SPLIT(service, ',') as service
       , CURRENT_TIMESTAMP() AS processed_at
FROM `{project_id}.{bronze_dataset_id}.family_mart`
WHERE extract_date = '{target_date}'
"""

