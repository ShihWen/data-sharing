# This MERGE query handles SCD2 (Slowly Changing Dimension Type 2) for road network data.
# It deduplicates the staging table by keeping the most complete record for each osmid
# before performing the merge operation to prevent "UPDATE/MERGE must match at most one source row" errors.
MERGE_SCD2_INTERCITY_BUS_ROUTE = """
MERGE INTO `{project_id}.{dataset_id}.{table_id}` AS T
USING (
    SELECT * FROM (
        SELECT
            *
            , ROW_NUMBER() OVER (
                PARTITION BY sub_route_uid
                ORDER BY update_time DESC
            ) as rn
        FROM `{project_id}.{dataset_id}.{staging_table_id}`
    ) ranked
    WHERE rn = 1
) AS S
ON T.sub_route_uid = S.sub_route_uid AND T.is_current = TRUE
WHEN MATCHED AND T.update_time < S.update_time THEN
    UPDATE SET
        valid_to_ts = CURRENT_TIMESTAMP(),
        is_current = FALSE
WHEN NOT MATCHED BY TARGET THEN
    INSERT (
        route_uid
        , route_id
        , route_name_zh_tw
        , route_name_en
        , sub_route_uid
        , sub_route_id
        , sub_route_name_zh_tw
        , sub_route_name_en
        , direction
        , update_time
        , version_id
        , geometry
        , processed_at
        , valid_from_ts
        , valid_to_ts
        , is_current
    )
    VALUES (
        S.route_uid
        , S.route_id
        , S.route_name_zh_tw
        , S.route_name_en
        , S.sub_route_uid
        , S.sub_route_id
        , S.sub_route_name_zh_tw
        , S.sub_route_name_en
        , S.direction
        , S.update_time
        , S.version_id
        , S.geometry
        , CURRENT_TIMESTAMP()
        , CURRENT_TIMESTAMP()
        , TIMESTAMP('9999-12-31T23:59:59')
        , TRUE
    );
"""

INSERT_UPDATED_INTERCITY_BUS_ROUTE = """
INSERT INTO `{project_id}.{dataset_id}.{table_id}` (
    route_uid
    , route_id
    , route_name_zh_tw
    , route_name_en
    , sub_route_uid
    , sub_route_id
    , sub_route_name_zh_tw
    , sub_route_name_en
    , direction
    , update_time
    , version_id
    , geometry
    , processed_at
    , valid_from_ts
    , valid_to_ts
    , is_current
)
SELECT
    S.route_uid
    , S.route_id
    , S.route_name_zh_tw
    , S.route_name_en
    , S.sub_route_uid
    , S.sub_route_id
    , S.sub_route_name_zh_tw
    , S.sub_route_name_en
    , S.direction
    , S.update_time
    , S.version_id
    , S.geometry
    , CURRENT_TIMESTAMP() --AS processed_at
    , CURRENT_TIMESTAMP() --AS valid_from_ts
    , TIMESTAMP('9999-12-31T23:59:59') --AS valid_to_ts
    , TRUE --AS is_current
FROM (
    SELECT * FROM (
        SELECT
            *
            , ROW_NUMBER() OVER (
                PARTITION BY sub_route_uid
                ORDER BY update_time DESC
            ) as rn
        FROM `{project_id}.{dataset_id}.{staging_table_id}`
    ) ranked
    WHERE rn = 1
) AS S
JOIN `{project_id}.{dataset_id}.{table_id}` AS T
ON S.sub_route_uid = T.sub_route_uid
WHERE T.valid_to_ts = (
    SELECT MAX(T2.valid_to_ts)
    FROM `{project_id}.{dataset_id}.{table_id}` T2
    WHERE T2.sub_route_uid = T.sub_route_uid
)
AND T.is_current = FALSE;
"""

MERGE_SCD2_INTERCITY_BUS_STATION = """
MERGE INTO `{project_id}.{dataset_id}.{table_id}` AS T
USING (
    SELECT * FROM (
        SELECT
            *
            , ROW_NUMBER() OVER (
                PARTITION BY station_uid
                ORDER BY update_time DESC
            ) as rn
        FROM `{project_id}.{dataset_id}.{staging_table_id}`
    ) ranked
    WHERE rn = 1
) AS S
ON T.station_uid = S.station_uid AND T.is_current = TRUE
WHEN MATCHED AND T.update_time < S.update_time THEN
    UPDATE SET
        valid_to_ts = CURRENT_TIMESTAMP(),
        is_current = FALSE
WHEN NOT MATCHED BY TARGET THEN
    INSERT (
        station_uid,
        station_id,
        station_name,
        station_position,
        station_group_id,
        stops,
        location_city_code,
        bearing,
        update_time,
        version_id,
        geometry,
        processed_at,
        valid_from_ts,
        valid_to_ts,
        is_current
    )
    VALUES (
        S.station_uid,
        S.station_id,
        S.station_name,
        S.station_position,
        S.station_group_id,
        S.stops,
        S.location_city_code,
        S.bearing,
        S.update_time,
        S.version_id,
        ST_GEOGFROMTEXT(S.geometry),
        CURRENT_TIMESTAMP(),
        CURRENT_TIMESTAMP(),
        TIMESTAMP('9999-12-31T23:59:59'),
        TRUE
    );
"""

INSERT_UPDATED_INTERCITY_BUS_STATION = """
INSERT INTO `{project_id}.{dataset_id}.{table_id}` (
    station_uid,
    station_id,
    station_name,
    station_position,
    station_group_id,
    stops,
    location_city_code,
    bearing,
    update_time,
    version_id,
    geometry,
    processed_at,
    valid_from_ts,
    valid_to_ts,
    is_current
)
SELECT
    S.station_uid,
    S.station_id,
    S.station_name,
    S.station_position,
    S.station_group_id,
    S.stops,
    S.location_city_code,
    S.bearing,
    S.update_time,
    S.version_id,
    ST_GEOGFROMTEXT(S.geometry) AS geometry,
    CURRENT_TIMESTAMP() AS processed_at,
    CURRENT_TIMESTAMP() AS valid_from_ts,
    TIMESTAMP('9999-12-31T23:59:59') AS valid_to_ts,
    TRUE AS is_current
FROM (
    SELECT * FROM (
        SELECT
            *
            , ROW_NUMBER() OVER (
                PARTITION BY station_uid
                ORDER BY update_time DESC
            ) as rn
        FROM `{project_id}.{dataset_id}.{staging_table_id}`
    ) ranked
    WHERE rn = 1
) AS S
JOIN `{project_id}.{dataset_id}.{table_id}` AS T
ON S.station_uid = T.station_uid
WHERE T.valid_to_ts = (
    SELECT MAX(T2.valid_to_ts)
    FROM `{project_id}.{dataset_id}.{table_id}` T2
    WHERE T2.station_uid = T.station_uid
)
AND T.is_current = FALSE;
"""

MERGE_SCD2_CITY_BUS_ROUTE = """
MERGE INTO `{project_id}.{dataset_id}.{table_id}` AS T
USING (
    SELECT * FROM (
        SELECT
            *
            , ROW_NUMBER() OVER (
                PARTITION BY route_uid, sub_route_uid, direction
                ORDER BY update_time DESC
            ) as rn
        FROM `{project_id}.{dataset_id}.{staging_table_id}`
    ) ranked
    WHERE rn = 1
) AS S
ON T.route_uid = S.route_uid AND 
T.sub_route_uid = S.sub_route_uid AND
T.direction = S.direction AND
T.is_current = TRUE
WHEN MATCHED AND T.update_time < S.update_time THEN
    UPDATE SET
        valid_to_ts = CURRENT_TIMESTAMP(),
        is_current = FALSE
WHEN NOT MATCHED BY TARGET THEN
    INSERT (
        route_uid
        , route_id
        , route_name_zh_tw
        , route_name_en
        , sub_route_uid
        , sub_route_id
        , sub_route_name_zh_tw
        , sub_route_name_en
        , direction
        , update_time
        , version_id
        , geometry
        , city
        , processed_at
        , valid_from_ts
        , valid_to_ts
        , is_current
    )
    VALUES (
        S.route_uid
        , S.route_id
        , S.route_name_zh_tw
        , S.route_name_en
        , S.sub_route_uid
        , S.sub_route_id
        , S.sub_route_name_zh_tw
        , S.sub_route_name_en
        , S.direction
        , S.update_time
        , S.version_id
        , S.geometry
        , S.city
        , CURRENT_TIMESTAMP()
        , CURRENT_TIMESTAMP()
        , TIMESTAMP('9999-12-31T23:59:59')
        , TRUE
    );
"""

INSERT_UPDATED_CITY_BUS_ROUTE = """
INSERT INTO `{project_id}.{dataset_id}.{table_id}` (
    route_uid
    , route_id
    , route_name_zh_tw
    , route_name_en
    , sub_route_uid
    , sub_route_id
    , sub_route_name_zh_tw
    , sub_route_name_en
    , direction
    , update_time
    , version_id
    , geometry
    , city
    , processed_at
    , valid_from_ts
    , valid_to_ts
    , is_current
)
SELECT
    S.route_uid
    , S.route_id
    , S.route_name_zh_tw
    , S.route_name_en
    , S.sub_route_uid
    , S.sub_route_id
    , S.sub_route_name_zh_tw
    , S.sub_route_name_en
    , S.direction
    , S.update_time
    , S.version_id
    , S.geometry
    , S.city
    , CURRENT_TIMESTAMP() --AS processed_at
    , CURRENT_TIMESTAMP() --AS valid_from_ts
    , TIMESTAMP('9999-12-31T23:59:59') --AS valid_to_ts
    , TRUE --AS is_current
FROM (
    SELECT * FROM (
        SELECT
            *
            , ROW_NUMBER() OVER (
                PARTITION BY route_uid, sub_route_uid, direction
                ORDER BY update_time DESC
            ) as rn
        FROM `{project_id}.{dataset_id}.{staging_table_id}`
    ) ranked
    WHERE rn = 1
) AS S
JOIN `{project_id}.{dataset_id}.{table_id}` AS T
ON S.sub_route_uid = T.sub_route_uid AND
S.direction = T.direction AND
S.route_uid = T.route_uid
WHERE T.valid_to_ts = (
    SELECT MAX(T2.valid_to_ts)
    FROM `{project_id}.{dataset_id}.{table_id}` T2
    WHERE 
    T2.route_uid = T.route_uid AND
    T2.sub_route_uid = T.sub_route_uid AND
    T2.direction = T.direction
)
AND T.is_current = FALSE;
"""

MERGE_SCD2_CITY_BUS_STATION = """
MERGE INTO `{project_id}.{dataset_id}.{table_id}` AS T
USING (
    SELECT * FROM (
        SELECT
            *
            , ROW_NUMBER() OVER (
                PARTITION BY station_uid
                ORDER BY update_time DESC
            ) as rn
        FROM `{project_id}.{dataset_id}.{staging_table_id}`
    ) ranked
    WHERE rn = 1
) AS S
ON T.station_uid = S.station_uid AND T.is_current = TRUE
WHEN MATCHED AND T.update_time < S.update_time THEN
    UPDATE SET
        valid_to_ts = CURRENT_TIMESTAMP(),
        is_current = FALSE
WHEN NOT MATCHED BY TARGET THEN
    INSERT (
        station_uid,
        station_id,
        station_name,
        station_position,
        station_group_id,
        stops,
        location_city_code,
        bearing,
        update_time,
        version_id,
        geometry,
        city,
        processed_at,
        valid_from_ts,
        valid_to_ts,
        is_current
    )
    VALUES (
        S.station_uid,
        S.station_id,
        S.station_name,
        S.station_position,
        S.station_group_id,
        S.stops,
        S.location_city_code,
        S.bearing,
        S.update_time,
        S.version_id,
        ST_GEOGFROMTEXT(S.geometry),
        S.city,
        CURRENT_TIMESTAMP(),
        CURRENT_TIMESTAMP(),
        TIMESTAMP('9999-12-31T23:59:59'),
        TRUE
    );
"""

INSERT_UPDATED_CITY_BUS_STATION = """
INSERT INTO `{project_id}.{dataset_id}.{table_id}` (
    station_uid,
    station_id,
    station_name,
    station_position,
    station_group_id,
    stops,
    location_city_code,
    bearing,
    update_time,
    version_id,
    geometry,
    city,
    processed_at,
    valid_from_ts,
    valid_to_ts,
    is_current
)
SELECT
    S.station_uid,
    S.station_id,
    S.station_name,
    S.station_position,
    S.station_group_id,
    S.stops,
    S.location_city_code,
    S.bearing,
    S.update_time,
    S.version_id,
    ST_GEOGFROMTEXT(S.geometry) AS geometry,
    S.city,
    CURRENT_TIMESTAMP() --AS processed_at,
    CURRENT_TIMESTAMP() --AS valid_from_ts,
    TIMESTAMP('9999-12-31T23:59:59') --AS valid_to_ts,
    TRUE --AS is_current
FROM (
    SELECT * FROM (
        SELECT
            *
            , ROW_NUMBER() OVER (
                PARTITION BY station_uid
                ORDER BY update_time DESC
            ) as rn
        FROM `{project_id}.{dataset_id}.{staging_table_id}`
    ) ranked
    WHERE rn = 1
) AS S
JOIN `{project_id}.{dataset_id}.{table_id}` AS T
ON S.station_uid = T.station_uid
WHERE T.valid_to_ts = (
    SELECT MAX(T2.valid_to_ts)
    FROM `{project_id}.{dataset_id}.{table_id}` T2
    WHERE T2.station_uid = T.station_uid
)
AND T.is_current = FALSE;
"""


##############################################################  Intercity Bus Stop of Route

MERGE_SCD2_INTERCITY_BUS_STOP_OF_ROUTE = """
MERGE INTO `{project_id}.{dataset_id}.{table_id}` AS T
USING (
    -- 定義核心邏輯：找出變更並產生對應的 MERGE 動作
    WITH Staging AS (
        SELECT * EXCEPT(rn) FROM (
            SELECT
                * EXCEPT(operators), -- 排除 operators 欄位
                ROW_NUMBER() OVER (
                    PARTITION BY route_uid, sub_route_uid, direction
                    ORDER BY update_time DESC
                ) as rn
            FROM `{project_id}.{dataset_id}.{staging_table_id}`
        )
        WHERE rn = 1
    ),
    Changes AS (
        SELECT
            S.route_uid,
            S.route_id,
            S.route_name,
            S.sub_route_uid,
            S.sub_route_id,
            S.sub_route_name,
            S.direction,
            S.stops,
            S.update_time,
            S.version_id,
            -- 判斷是新資料(NEW)、資料更新(CHANGED) 還是無變更(NO_CHANGE)
            CASE
                WHEN T.sub_route_uid IS NULL THEN 'NEW'
                WHEN S.update_time > T.update_time THEN 'CHANGED'
                ELSE 'NO_CHANGE'
            END as change_type
        FROM Staging S
        LEFT JOIN `{project_id}.{dataset_id}.{table_id}` T
        ON S.route_uid = T.route_uid
        AND S.sub_route_uid = T.sub_route_uid
        AND S.direction = T.direction
        AND T.is_current = TRUE
    )
    -- 【關鍵技巧】將 CHANGED 拆解成兩筆動作：
    -- 1. INSERT (用於寫入新版本) - 適用於 NEW 和 CHANGED
    SELECT *, 'INSERT' as merge_action FROM Changes WHERE change_type IN ('NEW', 'CHANGED')
    UNION ALL
    -- 2. CLOSE (用於關閉舊版本) - 僅適用於 CHANGED
    SELECT *, 'CLOSE' as merge_action FROM Changes WHERE change_type = 'CHANGED'
) AS S
ON T.route_uid = S.route_uid
AND T.sub_route_uid = S.sub_route_uid
AND T.direction = S.direction
AND T.is_current = TRUE
AND S.merge_action = 'CLOSE' -- 只有標記為 CLOSE 的動作才去匹配並更新舊資料

-- 動作 1: 關閉舊資料
WHEN MATCHED THEN
    UPDATE SET
        valid_to_ts = CURRENT_TIMESTAMP(),
        is_current = FALSE

-- 動作 2: 插入新資料
WHEN NOT MATCHED AND S.merge_action = 'INSERT' THEN
    INSERT (
        route_uid, route_id, route_name,
        sub_route_uid, sub_route_id, sub_route_name,
        direction, stops,
        update_time, version_id,
        processed_at, valid_from_ts, valid_to_ts, is_current
    )
    VALUES (
        S.route_uid, S.route_id, S.route_name,
        S.sub_route_uid, S.sub_route_id, S.sub_route_name,
        S.direction, S.stops,
        S.update_time, S.version_id,
        CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), TIMESTAMP('9999-12-31 23:59:59'), TRUE
    );
"""