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

MERGE_SCD2_TOWNS = """
MERGE INTO `{project_id}.{dataset_id}.dim_towns` AS T
USING `{project_id}.{dataset_id}.dim_towns_staging` AS S
ON T.town_code = S.town_code AND T.is_current = TRUE
WHEN MATCHED AND T.update_date < S.update_date THEN
    UPDATE SET
        valid_to_ts = CURRENT_TIMESTAMP(),
        is_current = FALSE
WHEN NOT MATCHED BY TARGET THEN
    INSERT (
        town_code, town_name_zh, city_name_en, city_name_zh, geometry, 
        update_date, check_date, processed_at, valid_from_ts, valid_to_ts, is_current
    )
    VALUES (
        S.town_code, S.town_name_zh, S.city_name_en, S.city_name_zh, S.geometry,
        S.update_date, S.check_date, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), 
        TIMESTAMP('9999-12-31T23:59:59'), TRUE
    );
"""

INSERT_UPDATED_TOWNS = """
INSERT INTO `{project_id}.{dataset_id}.dim_towns` (
    town_code, town_name_zh, city_name_en, city_name_zh, geometry, 
    update_date, check_date, processed_at, valid_from_ts, valid_to_ts, is_current
)
SELECT
    S.town_code,
    S.town_name_zh,
    S.city_name_en,
    S.city_name_zh,
    S.geometry,
    S.update_date,
    S.check_date,
    CURRENT_TIMESTAMP() AS processed_at,
    CURRENT_TIMESTAMP() AS valid_from_ts,
    TIMESTAMP('9999-12-31T23:59:59') AS valid_to_ts,
    TRUE AS is_current
FROM `{project_id}.{dataset_id}.dim_towns_staging` AS S
JOIN `{project_id}.{dataset_id}.dim_towns` AS T
ON S.town_code = T.town_code
WHERE T.valid_to_ts = (
    SELECT MAX(T2.valid_to_ts)
    FROM `{project_id}.{dataset_id}.dim_towns` T2
    WHERE T2.town_code = T.town_code
)
AND T.is_current = FALSE;
"""

MERGE_SCD2_VILLAGES = """
MERGE INTO `{project_id}.{dataset_id}.dim_villages` AS T
USING `{project_id}.{dataset_id}.dim_villages_staging` AS S
ON T.village_code = S.village_code AND T.is_current = TRUE
WHEN MATCHED AND T.update_date < S.update_date THEN
    UPDATE SET
        valid_to_ts = CURRENT_TIMESTAMP(),
        is_current = FALSE
WHEN NOT MATCHED BY TARGET THEN
    INSERT (
        village_code, village_name_zh, town_code, town_name_zh, city_name_en, city_name_zh, 
        geometry, update_date, check_date, processed_at, valid_from_ts, valid_to_ts, is_current
    )
    VALUES (
        S.village_code, S.village_name_zh, S.town_code, S.town_name_zh, S.city_name_en, S.city_name_zh,
        S.geometry, S.update_date, S.check_date, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), 
        TIMESTAMP('9999-12-31T23:59:59'), TRUE
    );
"""

INSERT_UPDATED_VILLAGES = """
INSERT INTO `{project_id}.{dataset_id}.dim_villages` (
    village_code, village_name_zh, town_code, town_name_zh, city_name_en, city_name_zh, 
    geometry, update_date, check_date, processed_at, valid_from_ts, valid_to_ts, is_current
)
SELECT
    S.village_code,
    S.village_name_zh,
    S.town_code,
    S.town_name_zh,
    S.city_name_en,
    S.city_name_zh,
    S.geometry,
    S.update_date,
    S.check_date,
    CURRENT_TIMESTAMP() AS processed_at,
    CURRENT_TIMESTAMP() AS valid_from_ts,
    TIMESTAMP('9999-12-31T23:59:59') AS valid_to_ts,
    TRUE AS is_current
FROM `{project_id}.{dataset_id}.dim_villages_staging` AS S
JOIN `{project_id}.{dataset_id}.dim_villages` AS T
ON S.village_code = T.village_code
WHERE T.valid_to_ts = (
    SELECT MAX(T2.valid_to_ts)
    FROM `{project_id}.{dataset_id}.dim_villages` T2
    WHERE T2.village_code = T.village_code
)
AND T.is_current = FALSE;
""" 