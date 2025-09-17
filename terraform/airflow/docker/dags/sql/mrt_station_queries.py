# -*- coding: utf-8 -*-
"""
SQL queries for the mrt_station_bronze_to_silver DAG.
"""

CHECK_NEW_VERSIONS_QUERY = """
WITH bronze_versions AS (
    SELECT VersionID FROM `{{ var.value.gcp_project_id }}.tpe_mrt_bronze.mrt_station`
    UNION ALL
    SELECT VersionID FROM `{{ var.value.gcp_project_id }}.tpe_mrt_bronze.mrt_station_ntmc`
)
SELECT COUNT(DISTINCT b.VersionID)
FROM bronze_versions b
WHERE NOT EXISTS (
    SELECT 1
    FROM `{{ var.value.gcp_project_id }}.tpe_mrt_silver.mrt_station` s
    WHERE s.version_id = b.VersionID
);
"""

MERGE_SCD2_MRT_STATION = """
/*
This query implements SCD2 (Slowly Changing Dimension Type 2) for MRT station data.
It handles both new stations and updates to existing stations by maintaining historical versions.
*/

MERGE `{{ var.value.gcp_project_id }}.{{ params.silver_dataset }}.mrt_station` AS T
USING (
  WITH bronze_stations AS (
    SELECT * FROM `{{ var.value.gcp_project_id }}.{{ params.bronze_dataset }}.mrt_station`
    UNION ALL
    SELECT * FROM `{{ var.value.gcp_project_id }}.{{ params.bronze_dataset }}.mrt_station_ntmc`
  )
  SELECT
    *,
    -- Use a regex to parse the StationAddress
    -- Example: "105008臺北市松山區敦化北路338號"
    -- Group 1 (postal_code): (\d{5, 6})
    -- Group 2 (city): (.*?市|.*?縣)
    -- Group 3 (town): (.*?區|.*?鄉|.*?鎮|.*?市)
    -- Group 4 (street_address): (.*)
    REGEXP_EXTRACT(StationAddress, r'(\d{5,6})') AS parsed_postal_code,
    REGEXP_EXTRACT(StationAddress, r'\d{5,6}(.*?市|.*?縣)') AS parsed_city,
    REGEXP_EXTRACT(StationAddress, r'\d{5,6}.*?[市縣](.*?區|.*?鄉|.*?鎮|.*?市)') AS parsed_town,
    REGEXP_EXTRACT(StationAddress, r'\d{5,6}.*?[市縣].*?[區鄉鎮市](.*)') AS parsed_street_address
  FROM
    bronze_stations
  WHERE VersionID NOT IN (SELECT DISTINCT version_id FROM `{{ var.value.gcp_project_id }}.{{ params.silver_dataset }}.mrt_station` WHERE version_id IS NOT NULL)
) AS S
ON T.station_uid = S.StationUID AND T.is_current = TRUE

WHEN MATCHED AND (
    T.station_id <> S.StationID OR
    T.station_name.zh_tw <> S.StationName_Zh_tw OR
    T.station_name.en <> S.StationName_En OR
    T.station_address <> S.StationAddress OR
    T.location.postal_code <> S.parsed_postal_code OR
    T.location.city <> S.parsed_city OR
    T.location.town <> S.parsed_town OR
    T.location.street_address <> S.parsed_street_address OR
    T.bike_allow_on_holiday <> S.BikeAllowOnHoliday OR
    T.src_update_time <> TIMESTAMP(S.SrcUpdateTime) OR
    T.update_time <> TIMESTAMP(S.UpdateTime) OR
    ST_EQUALS(T.station_position, ST_GEOGPOINT(S.StationPosition_PositionLon, S.StationPosition_PositionLat)) = FALSE
) THEN
  UPDATE SET
    is_current = FALSE,
    valid_to_ts = CURRENT_TIMESTAMP()

WHEN NOT MATCHED BY TARGET THEN
  INSERT (
    station_uid,
    station_id,
    station_name,
    station_address,
    location,
    station_position,
    geohash,
    bike_allow_on_holiday,
    src_update_time,
    update_time,
    version_id,
    -- Data quality fields
    is_valid_location,
    is_complete_record,
    data_quality_score,
    -- Processing metadata
    processed_at,
    -- SCD2 fields
    valid_from_ts,
    valid_to_ts,
    is_current
  )
  VALUES (
    S.StationUID,
    S.StationID,
    -- STRUCT for station names
    STRUCT(
      S.StationName_Zh_tw AS zh_tw,
      S.StationName_En AS en
    ),
    S.StationAddress,
    -- STRUCT for location details
    STRUCT(
      S.parsed_postal_code AS postal_code,
      S.parsed_city AS city,  
      S.parsed_town AS town,
      S.parsed_street_address AS street_address
    ),
    -- Create GEOGRAPHY point from lat/lon
    ST_GEOGPOINT(S.StationPosition_PositionLon, S.StationPosition_PositionLat),
    S.StationPosition_GeoHash,
    S.BikeAllowOnHoliday,
    -- Cast update times to TIMESTAMP
    TIMESTAMP(S.SrcUpdateTime),
    TIMESTAMP(S.UpdateTime),
    S.VersionID,
    -- Data quality checks
    (S.StationPosition_PositionLon BETWEEN 120 AND 122) AND (S.StationPosition_PositionLat BETWEEN 20 AND 26), -- Simple check for Taiwan area
    (S.StationUID IS NOT NULL AND S.StationID IS NOT NULL AND S.StationName_Zh_tw IS NOT NULL AND S.StationAddress IS NOT NULL), -- Check for completeness
    -- Calculate quality score (example: 1.0 if complete, 0.5 otherwise)
    CASE
      WHEN (S.StationUID IS NOT NULL AND S.StationID IS NOT NULL AND S.StationName_Zh_tw IS NOT NULL AND S.StationAddress IS NOT NULL) THEN 1.0
      ELSE 0.5
    END,
    -- Processing timestamp
    CURRENT_TIMESTAMP(),
    -- SCD2 fields
    CURRENT_TIMESTAMP(),
    TIMESTAMP('9999-12-31T23:59:59'),
    TRUE
  )
"""

# We need a second query to insert the updated rows for the matched records.
INSERT_UPDATED_MRT_STATION = """
INSERT INTO `{{ var.value.gcp_project_id }}.{{ params.silver_dataset }}.mrt_station` (
    station_uid,
    station_id,
    station_name,
    station_address,
    location,
    station_position,
    geohash,
    bike_allow_on_holiday,
    src_update_time,
    update_time,
    version_id,
    -- Data quality fields
    is_valid_location,
    is_complete_record,
    data_quality_score,
    -- Processing metadata
    processed_at,
    -- SCD2 fields
    valid_from_ts,
    valid_to_ts,
    is_current
)
SELECT
    S.StationUID,
    S.StationID,
    -- STRUCT for station names
    STRUCT(
      S.StationName_Zh_tw AS zh_tw,
      S.StationName_En AS en
    ),
    S.StationAddress,
    -- STRUCT for location details
    STRUCT(
      S.parsed_postal_code AS postal_code,
      S.parsed_city AS city,  
      S.parsed_town AS town,
      S.parsed_street_address AS street_address
    ),
    -- Create GEOGRAPHY point from lat/lon
    ST_GEOGPOINT(S.StationPosition_PositionLon, S.StationPosition_PositionLat),
    S.StationPosition_GeoHash,
    S.BikeAllowOnHoliday,
    -- Cast update times to TIMESTAMP
    TIMESTAMP(S.SrcUpdateTime),
    TIMESTAMP(S.UpdateTime),
    S.VersionID,
    -- Data quality checks
    (S.StationPosition_PositionLon BETWEEN 120 AND 122) AND (S.StationPosition_PositionLat BETWEEN 20 AND 26), -- Simple check for Taiwan area
    (S.StationUID IS NOT NULL AND S.StationID IS NOT NULL AND S.StationName_Zh_tw IS NOT NULL AND S.StationAddress IS NOT NULL), -- Check for completeness
    -- Calculate quality score (example: 1.0 if complete, 0.5 otherwise)
    CASE
      WHEN (S.StationUID IS NOT NULL AND S.StationID IS NOT NULL AND S.StationName_Zh_tw IS NOT NULL AND S.StationAddress IS NOT NULL) THEN 1.0
      ELSE 0.5
    END,
    -- Processing timestamp
    CURRENT_TIMESTAMP(),
    -- SCD2 fields
    CURRENT_TIMESTAMP(),
    TIMESTAMP('9999-12-31T23:59:59'),
    TRUE
FROM (
  WITH bronze_stations AS (
    SELECT * FROM `{{ var.value.gcp_project_id }}.{{ params.bronze_dataset }}.mrt_station`
    UNION ALL
    SELECT * FROM `{{ var.value.gcp_project_id }}.{{ params.bronze_dataset }}.mrt_station_ntmc`
  )
  SELECT
    *,
    -- Use a regex to parse the StationAddress
    REGEXP_EXTRACT(StationAddress, r'(\d{5,6})') AS parsed_postal_code,
    REGEXP_EXTRACT(StationAddress, r'\d{5,6}(.*?市|.*?縣)') AS parsed_city,
    REGEXP_EXTRACT(StationAddress, r'\d{5,6}.*?[市縣](.*?區|.*?鄉|.*?鎮|.*?市)') AS parsed_town,
    REGEXP_EXTRACT(StationAddress, r'\d{5,6}.*?[市縣].*?[區鄉鎮市](.*)') AS parsed_street_address
  FROM
    bronze_stations
  WHERE VersionID NOT IN (SELECT DISTINCT version_id FROM `{{ var.value.gcp_project_id }}.{{ params.silver_dataset }}.mrt_station` WHERE version_id IS NOT NULL)
) AS S
JOIN `{{ var.value.gcp_project_id }}.{{ params.silver_dataset }}.mrt_station` AS T
ON S.StationUID = T.station_uid
WHERE T.valid_to_ts = (
    SELECT MAX(T2.valid_to_ts)
    FROM `{{ var.value.gcp_project_id }}.{{ params.silver_dataset }}.mrt_station` T2
    WHERE T2.station_uid = T.station_uid
)
AND T.is_current = FALSE;
""" 