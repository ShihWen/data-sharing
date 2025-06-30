WITH
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
  monthly_output AS (
    SELECT
      year_month,
      PARSE_DATE('%Y-%m', year_month) as year_month_date,
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
SELECT
  A.year_month_date,
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