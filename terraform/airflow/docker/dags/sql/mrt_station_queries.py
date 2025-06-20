# -*- coding: utf-8 -*-
"""
SQL queries for the mrt_station_bronze_to_silver DAG.
"""

CHECK_NEW_VERSIONS_QUERY = """
SELECT COUNT(b.VersionID)
FROM `{{ var.value.gcp_project_id }}.tpe_mrt_bronze.mrt_station` b
WHERE NOT EXISTS (
    SELECT 1
    FROM `{{ var.value.gcp_project_id }}.tpe_mrt_silver.mrt_station` s
    WHERE s.version_id = b.VersionID
);
"""

TRANSFORM_AND_LOAD_SQL = """
/*
This query transforms and inserts new MRT station data from the bronze layer
into the silver layer. It ensures that only new versions are processed.
*/

MERGE `{{ var.value.gcp_project_id }}.{{ params.silver_dataset }}.mrt_station` AS T
USING (
  SELECT
    *,
    -- Use a regex to parse the StationAddress
    -- Example: "105008臺北市松山區敦化北路338號"
    -- Group 1 (postal_code): (\d{5, 6})
    -- Group 2 (city): (.*?市|.*?縣)
    -- Group 3 (town): (.*?區|.*?鄉|.*?鎮|.*?市)
    -- Group 4 (street_address): (.*)
    REGEXP_EXTRACT(StationAddress, r'(\d{5, 6})') AS parsed_postal_code,
    REGEXP_EXTRACT(StationAddress, r'\\d{5, 6}(.*?市|.*?縣)') AS parsed_city,
    REGEXP_EXTRACT(StationAddress, r'\\d{5, 6}.*?[市縣](.*?區|.*?鄉|.*?鎮|.*?市)') AS parsed_town,
    REGEXP_EXTRACT(StationAddress, r'\\d{5, 6}.*?[市縣].*?[區鄉鎮市](.*)') AS parsed_street_address
  FROM
    `{{ var.value.gcp_project_id }}.{{ params.bronze_dataset }}.mrt_station`
  WHERE VersionID NOT IN (SELECT DISTINCT version_id FROM `{{ var.value.gcp_project_id }}.{{ params.silver_dataset }}.mrt_station` WHERE version_id IS NOT NULL)
) AS S
ON T.station_uid = S.StationUID AND T.version_id = S.VersionID

WHEN NOT MATCHED THEN
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
    processed_at
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
      CAST(NULL AS STRING) AS city_code, -- No source for city_code
      S.parsed_town AS town,
      CAST(NULL AS STRING) AS town_code, -- No source for town_code
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
    CURRENT_TIMESTAMP()
  )
""" 