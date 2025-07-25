MERGE_SCD2_ROAD_NETWORK = """
MERGE INTO `{project_id}.{dataset_id}.{table_id}` AS T
USING `{project_id}.{dataset_id}.{staging_table_id}` AS S
ON T.osmid = S.osmid AND T.is_current = TRUE
WHEN MATCHED AND T.highway != S.highway OR T.name != S.name OR T.lanes != S.lanes OR T.oneway != S.oneway OR T.reversed != S.reversed OR T.length != S.length OR T.bridge != S.bridge OR T.maxspeed != S.maxspeed OR T.ref != S.ref OR T.service != S.service OR T.width != S.width OR T.access != S.access OR T.tunnel != S.tunnel OR T.junction != S.junction THEN
    UPDATE SET
        valid_to_ts = CURRENT_TIMESTAMP(),
        is_current = FALSE
WHEN NOT MATCHED BY TARGET THEN
    INSERT (
        u, v, osmid, city, district, highway, lanes, name, oneway, reversed, length,
        geometry, bridge, maxspeed, ref, service, width, access, tunnel, junction,
        processed_at, valid_from_ts, valid_to_ts, is_current
    )
    VALUES (
        S.u, S.v, S.osmid, S.city, S.district, S.highway, S.lanes, S.name, S.oneway, S.reversed, S.length,
        S.geometry, S.bridge, S.maxspeed, S.ref, S.service, S.width, S.access, S.tunnel, S.junction,
        CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), '9999-12-31T23:59:59', TRUE
    )
WHEN NOT MATCHED BY SOURCE AND T.is_current = TRUE THEN
    UPDATE SET
        valid_to_ts = CURRENT_TIMESTAMP(),
        is_current = FALSE;
""" 