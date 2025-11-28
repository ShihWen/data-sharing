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
    SELECT * FROM (
        SELECT
            *
            , ROW_NUMBER() OVER (
                PARTITION BY route_uid, sub_route_uid, direction, operator_no
                ORDER BY update_time DESC
            ) as rn
        FROM `{project_id}.{dataset_id}.{staging_table_id}`
    ) ranked
    WHERE rn = 1
) AS S
ON T.route_uid = S.route_uid AND 
T.sub_route_uid = S.sub_route_uid AND
T.direction = S.direction AND
T.operator_no = S.operator_no AND
T.is_current = TRUE
WHEN MATCHED AND T.update_time < S.update_time THEN
    UPDATE SET
        valid_to_ts = CURRENT_TIMESTAMP(),
        is_current = FALSE
WHEN NOT MATCHED BY TARGET THEN
    INSERT (
        route_uid
        , route_id
        , route_name
        , operators
        , sub_route_uid
        , sub_route_id
        , sub_route_name
        , direction
        , stops
        , update_time
        , version_id
        , processed_at
        , valid_from_ts
        , valid_to_ts
        , is_current
    )
    VALUES (
        S.route_uid
        , S.route_id
        , S.route_name
        , S.operators
        , S.sub_route_uid
        , S.sub_route_id
        , S.sub_route_name
        , S.direction
        , S.stops
        , S.update_time
        , S.version_id
        , CURRENT_TIMESTAMP()
        , CURRENT_TIMESTAMP()
        , TIMESTAMP('9999-12-31T23:59:59')
        , TRUE
    );
"""

INSERT_UPDATED_INTERCITY_BUS_STOP_OF_ROUTE = """
INSERT INTO `{project_id}.{dataset_id}.{table_id}` (
    route_uid
    , route_id
    , route_name
    , operators
    , sub_route_uid
    , sub_route_id
    , sub_route_name
    , direction
    , update_time
    , version_id
    , stops
    , processed_at
    , valid_from_ts
    , valid_to_ts
    , is_current
)
SELECT
    S.route_uid
    , S.route_id
    , S.route_name
    , S.operators
    , S.sub_route_uid
    , S.sub_route_id
    , S.sub_route_name
    , S.direction
    , S.update_time
    , S.version_id
    , S.stops
    , CURRENT_TIMESTAMP()
    , CURRENT_TIMESTAMP()
    , TIMESTAMP('9999-12-31T23:59:59')
    , TRUE
FROM (
    SELECT * FROM (
        SELECT
            *
            , ROW_NUMBER() OVER (
                PARTITION BY route_uid, sub_route_uid, direction, operator_no
                ORDER BY update_time DESC
            ) as rn
        FROM `{project_id}.{dataset_id}.{staging_table_id}`
    ) ranked
    WHERE rn = 1
) AS S
JOIN `{project_id}.{dataset_id}.{table_id}` AS T
ON S.sub_route_uid = T.sub_route_uid AND
S.direction = T.direction AND
S.operator_no = T.operator_no AND
S.route_uid = T.route_uid
WHERE T.valid_to_ts = (
    SELECT MAX(T2.valid_to_ts)
    FROM `{project_id}.{dataset_id}.{table_id}` T2
    WHERE 
    T2.route_uid = T.route_uid AND
    T2.sub_route_uid = T.sub_route_uid AND
    T2.direction = T.direction AND
    T2.operator_no = T.operator_no
)
AND T.is_current = FALSE;
"""