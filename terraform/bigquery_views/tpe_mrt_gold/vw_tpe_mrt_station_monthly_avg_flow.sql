-- This query calculates the monthly average traffic for each MRT station.
-- It is optimized to reduce the number of scans on the large `tpe_mrt_silver.mrt_traffic` table.

WITH
  -- Step 1: Aggregate traffic for both entrances and exits in a single pass.
  -- The UNNEST function is used to unpivot the entrance and exit columns,
  -- which is more efficient than scanning the table twice and joining the results.
  traffic_agg AS (
    SELECT
      FORMAT_DATE('%Y-%m', dt) AS year_month,
      station,
      SUM(CASE WHEN day_type = 'weekday' THEN traffic ELSE 0 END) AS weekday_traffic,
      SUM(CASE WHEN day_type = 'weekend' THEN traffic ELSE 0 END) AS weekend_traffic,
      SUM(traffic) AS total_traffic
    FROM
      `tpe_mrt_silver.mrt_traffic`,
      UNNEST([entrance, exit]) AS station
    GROUP BY
      1,
      2
  ),

  -- Step 2: Calculate the number of weekdays and weekend days for each month.
  -- This requires a separate scan to correctly count distinct days.
  day_counts AS (
    SELECT
      FORMAT_DATE('%Y-%m', dt) AS year_month,
      COUNTIF(day_type = 'weekday') AS weekday_days,
      COUNTIF(day_type = 'weekend') AS weekend_days,
      COUNT(*) AS total_days
    FROM (
      SELECT DISTINCT
        dt,
        day_type
      FROM
        `tpe_mrt_silver.mrt_traffic`
    )
    GROUP BY
      1
  ),

  -- Step 3: Join traffic data with day counts and calculate raw averages.
  -- SAFE_DIVIDE is used to prevent division-by-zero errors if a month has no weekdays or weekends.
  draft AS (
    SELECT
      A.year_month,
      A.station,
      SAFE_DIVIDE(A.total_traffic, B.total_days) AS avg_traffic_all_raw,
      SAFE_DIVIDE(A.weekday_traffic, B.weekday_days) AS avg_traffic_weekday_raw,
      SAFE_DIVIDE(A.weekend_traffic, B.weekend_days) AS avg_traffic_weekend_raw
    FROM
      traffic_agg AS A
      LEFT JOIN day_counts AS B ON A.year_month = B.year_month
  ),

  -- Step 4: Format the final output, including percentage change calculations.
  monthly_output AS (
    SELECT
      year_month,
      station,
      ROUND(avg_traffic_all_raw, 0) as avg_traffic_all,
      ROUND(avg_traffic_weekday_raw, 0) as avg_traffic_weekday,
      ROUND(avg_traffic_weekend_raw, 0) as avg_traffic_weekend,
      ROUND(
        SAFE_DIVIDE(
          (avg_traffic_weekend_raw - avg_traffic_weekday_raw),
          avg_traffic_weekday_raw
        ) * 100,
        1
      ) AS pct_change_vs_weekday,
      ROUND(
        SAFE_DIVIDE(
          (avg_traffic_weekend_raw - avg_traffic_weekday_raw),
          ((avg_traffic_weekend_raw + avg_traffic_weekday_raw) / 2)
        ) * 100,
        1
      ) AS pct_change_sym
    FROM
      draft
  ),

  -- Step 5: Get station metadata for joining.
  station_table AS (
    SELECT
      join_key,
      STRING_AGG(station_id, '/' ORDER BY station_id) AS station_id
    FROM (
      SELECT
        station_id,
        station_name.zh_tw,
        CASE
          WHEN station_name.zh_tw = '大橋頭' THEN '大橋頭站'
          WHEN station_id = 'BL07' THEN 'BL板橋'
          ELSE station_name.zh_tw
        END AS join_key
      FROM
        `tpe_mrt_silver.mrt_station`
    ) AS A
    GROUP BY
      join_key
  )

-- Final SELECT statement to assemble the view.
SELECT
  A.year_month,
  C.station_id,
  A.station,
  A.avg_traffic_all,
  A.avg_traffic_weekday,
  A.avg_traffic_weekend,
  A.pct_change_vs_weekday,
  A.pct_change_sym
FROM
  monthly_output AS A
  LEFT JOIN station_table AS C ON A.station = C.join_key
ORDER BY PARSE_DATE('%Y-%m', A.year_month), A.avg_traffic_all DESC; 