"""
SQL queries for MRT exit data processing from bronze to silver layer.
These queries are used by the mrt_exit_bronze_to_silver DAG.
Processing is based on VersionID to only load new versions.
"""

# Check for new versions in bronze that don't exist in silver
CHECK_NEW_VERSIONS_QUERY = """
WITH bronze_versions AS (
    SELECT DISTINCT VersionID
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_bronze_dataset_id }}.mrt_exit`
    WHERE VersionID IS NOT NULL
),
silver_versions AS (
    SELECT DISTINCT version_id
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_exit`
    WHERE version_id IS NOT NULL
),
new_versions AS (
    SELECT bronze_versions.VersionID
    FROM bronze_versions
    LEFT JOIN silver_versions ON bronze_versions.VersionID = silver_versions.version_id
    WHERE silver_versions.version_id IS NULL
    ORDER BY bronze_versions.VersionID
)
SELECT 
    COUNT(*) as new_version_count,
    MIN(VersionID) as min_new_version,
    MAX(VersionID) as max_new_version,
    CASE 
        WHEN COUNT(*) > 0 THEN true
        ELSE false
    END as has_new_versions
FROM new_versions
"""

# Transform and load new versions from bronze to silver
TRANSFORM_AND_LOAD_NEW_VERSIONS_QUERY = """
INSERT INTO `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_exit`
(
    station_id,
    exit_id,
    location_description,
    has_stairs,
    escalator_count,
    has_elevator,
    src_update_time,
    update_time,
    version_id,
    station_name_zh_tw,
    station_name_en,
    exit_name_zh_tw,
    exit_name_en,
    longitude,
    latitude,
    geohash,
    is_valid_location,
    is_complete_record,
    data_quality_score,
    is_accessible,
    total_mechanical_aids,
    accessibility_score,
    processed_at
)
WITH bronze_new_versions AS (
    SELECT b.*
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_bronze_dataset_id }}.mrt_exit` b
    LEFT JOIN `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_exit` s
        ON b.VersionID = s.version_id
    WHERE s.version_id IS NULL
        AND b.VersionID IS NOT NULL
)
SELECT
    -- Original fields (standardized naming)
    StationID as station_id,
    ExitID as exit_id,
    LocationDescription as location_description,
    Stair as has_stairs,
    Escalator as escalator_count,
    Elevator as has_elevator,
    
    -- Convert string timestamps to TIMESTAMP type
    CASE 
        WHEN SrcUpdateTime IS NOT NULL AND SrcUpdateTime != '' 
        THEN TIMESTAMP(SrcUpdateTime)
        ELSE NULL 
    END as src_update_time,
    
    CASE 
        WHEN UpdateTime IS NOT NULL AND UpdateTime != '' 
        THEN TIMESTAMP(UpdateTime)
        ELSE NULL 
    END as update_time,
    
    VersionID as version_id,
    StationName_Zh_tw as station_name_zh_tw,
    StationName_En as station_name_en,
    ExitName_Zh_tw as exit_name_zh_tw,
    ExitName_En as exit_name_en,
    ExitPosition_PositionLon as longitude,
    ExitPosition_PositionLat as latitude,
    ExitPosition_GeoHash as geohash,
    
    -- Data quality validation fields
    CASE 
        WHEN ExitPosition_PositionLon IS NULL OR ExitPosition_PositionLat IS NULL THEN false
        WHEN ExitPosition_PositionLon = 0 AND ExitPosition_PositionLat = 0 THEN false
        WHEN ExitPosition_PositionLon < 121.0 OR ExitPosition_PositionLon > 122.0 THEN false
        WHEN ExitPosition_PositionLat < 24.6 OR ExitPosition_PositionLat > 25.3 THEN false
        WHEN ExitPosition_GeoHash IS NULL THEN false
        ELSE true 
    END AS is_valid_location,
    
    CASE 
        WHEN StationID IS NULL OR TRIM(StationID) = '' THEN false
        WHEN ExitID IS NULL OR TRIM(ExitID) = '' THEN false
        WHEN StationName_Zh_tw IS NULL OR TRIM(StationName_Zh_tw) = '' THEN false
        WHEN ExitPosition_PositionLon IS NULL OR ExitPosition_PositionLat IS NULL THEN false
        ELSE true 
    END AS is_complete_record,
    
    -- Data quality score calculation (0.0 to 1.0)
    (
        -- Core fields (40% weight)
        CASE WHEN StationID IS NOT NULL AND TRIM(StationID) != '' THEN 0.1 ELSE 0 END +
        CASE WHEN ExitID IS NOT NULL AND TRIM(ExitID) != '' THEN 0.1 ELSE 0 END +
        CASE WHEN StationName_Zh_tw IS NOT NULL AND TRIM(StationName_Zh_tw) != '' THEN 0.1 ELSE 0 END +
        CASE WHEN StationName_En IS NOT NULL AND TRIM(StationName_En) != '' THEN 0.1 ELSE 0 END +
        
        -- Location fields (30% weight)
        CASE WHEN ExitPosition_PositionLon IS NOT NULL AND ExitPosition_PositionLon BETWEEN 121.0 AND 122.0 THEN 0.15 ELSE 0 END +
        CASE WHEN ExitPosition_PositionLat IS NOT NULL AND ExitPosition_PositionLat BETWEEN 24.6 AND 25.3 THEN 0.15 ELSE 0 END +
        
        -- Accessibility fields (20% weight)
        CASE WHEN Stair IS NOT NULL THEN 0.05 ELSE 0 END +
        CASE WHEN Escalator IS NOT NULL THEN 0.05 ELSE 0 END +
        CASE WHEN Elevator IS NOT NULL THEN 0.1 ELSE 0 END +
        
        -- Additional fields (10% weight)
        CASE WHEN LocationDescription IS NOT NULL AND TRIM(LocationDescription) != '' THEN 0.05 ELSE 0 END +
        CASE WHEN ExitPosition_GeoHash IS NOT NULL AND TRIM(ExitPosition_GeoHash) != '' THEN 0.05 ELSE 0 END
    ) AS data_quality_score,
    
    -- Derived business logic fields
    CASE WHEN Elevator = true THEN true ELSE false END AS is_accessible,
    COALESCE(Escalator, 0) + CASE WHEN Elevator = true THEN 1 ELSE 0 END AS total_mechanical_aids,
    
    -- Accessibility scoring (0-3 scale)
    CASE 
        WHEN Elevator = true AND Escalator > 0 THEN 3  -- Both
        WHEN Elevator = true THEN 2                    -- Elevator only
        WHEN Escalator > 0 THEN 1                      -- Escalator only
        ELSE 0                                          -- Stairs only
    END AS accessibility_score,
    
    -- Processing metadata
    CURRENT_TIMESTAMP() AS processed_at

FROM bronze_new_versions
"""

# Validate processing results
VALIDATE_PROCESSING_QUERY = """
WITH processing_stats AS (
    SELECT 
        COUNT(*) as records_processed,
        MIN(version_id) as min_version_processed,
        MAX(version_id) as max_version_processed,
        COUNT(CASE WHEN is_valid_location = false THEN 1 END) as invalid_location_records,
        COUNT(CASE WHEN is_complete_record = false THEN 1 END) as incomplete_records,
        AVG(data_quality_score) as avg_quality_score,
        COUNT(CASE WHEN is_accessible = true THEN 1 END) as accessible_exits
    FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_exit`
    WHERE processed_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
)
SELECT 
    *,
    CASE 
        WHEN records_processed > 0 THEN 'SUCCESS'
        ELSE 'NO_RECORDS_PROCESSED'
    END as status,
    ROUND((invalid_location_records * 100.0) / NULLIF(records_processed, 0), 2) as invalid_location_percentage,
    ROUND((incomplete_records * 100.0) / NULLIF(records_processed, 0), 2) as incomplete_percentage,
    ROUND((accessible_exits * 100.0) / NULLIF(records_processed, 0), 2) as accessibility_percentage
FROM processing_stats
"""

# Get summary of data quality for monitoring
DATA_QUALITY_SUMMARY_QUERY = """
SELECT 
    COUNT(*) as total_exits,
    COUNT(DISTINCT station_id) as total_stations,
    AVG(data_quality_score) as avg_quality_score,
    COUNT(CASE WHEN is_accessible = true THEN 1 END) as accessible_exits,
    COUNT(CASE WHEN accessibility_score = 3 THEN 1 END) as fully_equipped_exits,
    COUNT(CASE WHEN is_valid_location = false THEN 1 END) as invalid_location_exits,
    MIN(version_id) as min_version,
    MAX(version_id) as max_version,
    MAX(processed_at) as last_processed
FROM `{{ var.value.project_id }}.{{ var.value.tpe_mrt_silver_dataset_id }}.mrt_exit`
""" 