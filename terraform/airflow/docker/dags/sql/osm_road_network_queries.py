# This MERGE query handles SCD2 (Slowly Changing Dimension Type 2) for road network data.
# It deduplicates the staging table by keeping the most complete record for each osmid
# before performing the merge operation to prevent "UPDATE/MERGE must match at most one source row" errors.
MERGE_SCD2_ROAD_NETWORK = """
MERGE `{project_id}.{dataset_id}.{table_id}` AS T
USING (
    SELECT * FROM (
        SELECT 
            *,
            ROW_NUMBER() OVER (
                PARTITION BY osmid 
                ORDER BY 
                    (CASE WHEN name IS NOT NULL THEN 1 ELSE 0 END +
                     CASE WHEN highway IS NOT NULL THEN 1 ELSE 0 END +
                     CASE WHEN lanes IS NOT NULL THEN 1 ELSE 0 END +
                     CASE WHEN length IS NOT NULL THEN 1 ELSE 0 END +
                     CASE WHEN maxspeed IS NOT NULL THEN 1 ELSE 0 END +
                     CASE WHEN town_code IS NOT NULL THEN 1 ELSE 0 END) DESC,
                    name ASC,
                    highway ASC
            ) as rn
        FROM `{project_id}.{dataset_id}.{staging_table_id}`
    ) ranked
    WHERE rn = 1
) AS S
ON T.osmid = S.osmid AND T.is_current = TRUE
WHEN MATCHED AND (
    T.highway <> S.highway OR
    T.name <> S.name OR
    T.lanes <> S.lanes OR
    T.oneway <> S.oneway OR
    T.reversed <> S.reversed OR
    T.length <> S.length OR
    T.bridge <> S.bridge OR
    T.maxspeed <> S.maxspeed OR
    T.ref <> S.ref OR
    T.service <> S.service OR
    T.width <> S.width OR
    T.access <> S.access OR
    T.tunnel <> S.tunnel OR
    T.junction <> S.junction OR
    T.city <> S.city OR
    T.town <> S.town OR
    T.town_code <> S.town_code OR
    ST_EQUALS(T.geometry, S.geometry) = FALSE
) THEN
  UPDATE SET
    is_current = FALSE,
    valid_to_ts = CURRENT_TIMESTAMP()
WHEN NOT MATCHED BY TARGET THEN
  INSERT (
    osmid, u, v, highway, name, lanes, oneway, reversed, length, bridge,
    maxspeed, ref, service, width, access, tunnel, junction, geometry,
    city, town, town_code,
    processed_at, valid_from_ts, valid_to_ts, is_current
  ) VALUES (
    S.osmid, S.u, S.v, S.highway, S.name, S.lanes, S.oneway, S.reversed, S.length, S.bridge,
    S.maxspeed, S.ref, S.service, S.width, S.access, S.tunnel, S.junction, S.geometry,
    S.city, S.town, S.town_code,
    CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP(), TIMESTAMP('9999-12-31T23:59:59'), TRUE
  )
""" 