WITH day_counts AS (
  SELECT 
    FORMAT_DATE('%Y-%m', dt) AS year_month,
    COUNTIF(day_type = 'weekday') AS weekday_days,
    COUNTIF(day_type = 'weekend') AS weekend_days,
    COUNT(*) AS total_days
  FROM (
    SELECT DISTINCT dt, day_type
    FROM `tpe_mrt_silver.mrt_traffic`
  )
  GROUP BY year_month
),
entrance_data AS (
  SELECT FORMAT_DATE('%Y-%m', dt) AS year_month
        , entrance
        , EXTRACT(DAY FROM LAST_DAY(dt)) LAST_DT
        , SUM(traffic) entrance_all
        , SUM(CASE WHEN day_type = 'weekday' THEN traffic END) entrance_weekday
        , SUM(CASE WHEN day_type = 'weekend' THEN traffic END) entrance_weekend
  FROM `tpe_mrt_silver.mrt_traffic`
  GROUP BY year_month, entrance, LAST_DT
),
exit_data AS
(
  SELECT FORMAT_DATE('%Y-%m', dt) AS year_month
        , exit
        , EXTRACT(DAY FROM LAST_DAY(dt)) LAST_DT
        , SUM(traffic) exit_all
        , SUM(CASE WHEN day_type = 'weekday' THEN traffic END) exit_weekday
        , SUM(CASE WHEN day_type = 'weekend' THEN traffic END) exit_weekend
  FROM `tpe_mrt_silver.mrt_traffic`
  GROUP BY year_month, exit, LAST_DT
),
draft AS
(
  SELECT 
    A.year_month
    , A.entrance AS station
    , ROUND((A.entrance_all + B.exit_all) / D.total_days, 0) AS avg_traffic_all
    , ROUND((A.entrance_weekday + B.exit_weekday) / D.weekday_days, 0) AS avg_traffic_weekday
    , ROUND((A.entrance_weekend + B.exit_weekend) / D.weekend_days, 0) AS avg_traffic_weekend
  FROM entrance_data A
  LEFT JOIN exit_data B ON A.year_month = B.year_month AND A.entrance = B.exit
  LEFT JOIN day_counts D ON A.year_month = D.year_month
),
monthly_output AS
(
  SELECT year_month
        , PARSE_DATE('%Y-%m', year_month) year_month_join
        , DATE_ADD(PARSE_DATE('%Y-%m', year_month), INTERVAL 1 MONTH) AS next_month
        , station
        , avg_traffic_all
        , avg_traffic_weekday
        , avg_traffic_weekend
        , ROUND(
            (avg_traffic_weekend - avg_traffic_weekday) / 
            avg_traffic_weekday * 100
            , 1
            ) AS pct_change_vs_weekday
        , ROUND(
            (avg_traffic_weekend - avg_traffic_weekday) / 
            ((avg_traffic_weekend + avg_traffic_weekday) / 2) * 100
            , 1
          ) AS pct_change_sym
  FROM draft
),
station_table AS
(
  SELECT join_key
         , STRING_AGG(station_id,'/' ORDER BY station_id) station_id
  FROM
  (
    SELECT station_id
          , station_name.zh_tw
          , CASE WHEN station_name.zh_tw = '大橋頭' THEN '大橋頭站'
                  WHEN station_id = 'BL07' THEN 'BL板橋'
                  ELSE station_name.zh_tw 
            END AS join_key
    FROM `tpe_mrt_silver.mrt_station`
  ) A
  GROUP BY join_key
)
SELECT A.year_month
      , C.station_id
      , A.station
      , A.avg_traffic_all
      , A.avg_traffic_weekday
      , A.avg_traffic_weekend
      , A.pct_change_vs_weekday
      , A.pct_change_sym
    --   , B.year_month
    --   , B.avg_traffic_all
FROM monthly_output A
-- LEFT JOIN
-- (
--   SELECT year_month
--          , next_month
--          , station
--          , avg_traffic_all
--          , avg_traffic_weekday
--          , avg_traffic_weekend
--          , pct_change_vs_weekday
--          , pct_change_sym
--   FROM monthly_output
-- ) B ON A.year_month_join = B.next_month AND A.station = B.station
-- AND A.station = B.station
LEFT JOIN
station_table C ON A.station = C.join_key
ORDER BY PARSE_DATE('%Y-%m', A.year_month), A.avg_traffic_all DESC;