MERGE_SCD2_CITIES = """
MERGE INTO `{project_id}.{dataset_id}.{table_id}` AS T
USING `{project_id}.{dataset_id}.{staging_table_id}` AS S
ON T.city_name_en = S.city_name_en AND T.is_current = TRUE
WHEN MATCHED AND T.update_date < S.update_date THEN
    UPDATE SET
        valid_to_ts = CURRENT_TIMESTAMP(),
        is_current = FALSE
WHEN NOT MATCHED BY TARGET THEN
    INSERT (
        city_name_en, city_name_zh, geometry, update_date, check_date,
        processed_at, valid_from_ts, valid_to_ts, is_current
    )
    VALUES (
        S.city_name_en, S.city_name_zh, S.geometry, S.update_date, S.check_date,
        CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), TIMESTAMP('9999-12-31T23:59:59'), TRUE
    );
"""

# We need a second query to insert the updated rows for the matched records.
INSERT_UPDATED_CITIES = """
INSERT INTO `{project_id}.{dataset_id}.{table_id}` (
    city_name_en, city_name_zh, geometry, update_date, check_date,
    processed_at, valid_from_ts, valid_to_ts, is_current
)
SELECT
    S.city_name_en,
    S.city_name_zh,
    S.geometry,
    S.update_date,
    S.check_date,
    CURRENT_TIMESTAMP() AS processed_at,
    CURRENT_TIMESTAMP() AS valid_from_ts,
    TIMESTAMP('9999-12-31T23:59:59') AS valid_to_ts,
    TRUE AS is_current
FROM `{project_id}.{dataset_id}.{staging_table_id}` AS S
JOIN `{project_id}.{dataset_id}.{table_id}` AS T
ON S.city_name_en = T.city_name_en
WHERE T.valid_to_ts = (
    SELECT MAX(T2.valid_to_ts)
    FROM `{project_id}.{dataset_id}.{table_id}` T2
    WHERE T2.city_name_en = T.city_name_en
)
AND T.is_current = FALSE;
"""

MERGE_SCD2_DISTRICTS = """
MERGE INTO `{project_id}.{dataset_id}.dim_districts` AS T
USING `{project_id}.{dataset_id}.dim_districts_staging` AS S
ON T.district_code = S.district_code AND T.is_current = TRUE
WHEN MATCHED AND T.update_date < S.update_date THEN
    UPDATE SET
        valid_to_ts = CURRENT_TIMESTAMP(),
        is_current = FALSE
WHEN NOT MATCHED BY TARGET THEN
    INSERT (
        district_code, district_name_zh, city_name_en, city_name_zh, geometry, 
        update_date, check_date, processed_at, valid_from_ts, valid_to_ts, is_current
    )
    VALUES (
        S.district_code, S.district_name_zh, S.city_name_en, S.city_name_zh, S.geometry,
        S.update_date, S.check_date, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), 
        TIMESTAMP('9999-12-31T23:59:59'), TRUE
    );
"""

INSERT_UPDATED_DISTRICTS = """
INSERT INTO `{project_id}.{dataset_id}.dim_districts` (
    district_code, district_name_zh, city_name_en, city_name_zh, geometry, 
    update_date, check_date, processed_at, valid_from_ts, valid_to_ts, is_current
)
SELECT
    S.district_code,
    S.district_name_zh,
    S.city_name_en,
    S.city_name_zh,
    S.geometry,
    S.update_date,
    S.check_date,
    CURRENT_TIMESTAMP() AS processed_at,
    CURRENT_TIMESTAMP() AS valid_from_ts,
    TIMESTAMP('9999-12-31T23:59:59') AS valid_to_ts,
    TRUE AS is_current
FROM `{project_id}.{dataset_id}.dim_districts_staging` AS S
JOIN `{project_id}.{dataset_id}.dim_districts` AS T
ON S.district_code = T.district_code
WHERE T.valid_to_ts = (
    SELECT MAX(T2.valid_to_ts)
    FROM `{project_id}.{dataset_id}.dim_districts` T2
    WHERE T2.district_code = T.district_code
)
AND T.is_current = FALSE;
""" 