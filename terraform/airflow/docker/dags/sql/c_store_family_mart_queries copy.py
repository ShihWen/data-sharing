CHECK_NEW_DATA_QUERY = """
WITH bronze_dates AS (
    SELECT DISTINCT extract_date
    FROM `{project_id}.{bronze_dataset_id}`.family_mart
),
silver_dates AS (
    SELECT DISTINCT extract_date
    FROM `{project_id}.{silver_dataset_id}`.family_mart
),
new_date AS (
    SELECT bronze_dates.extract_date
    FROM bronze_dates
    LEFT JOIN silver_dates ON bronze_dates.extract_date = format_date('%Y-%m-%d', silver_dates.extract_date)
    WHERE silver_dates.extract_date IS NULL
    and bronze_dates.extract_date not like '%/%/%'
    ORDER BY bronze_dates.extract_date
    LIMIT 1  -- Only one date arrives at a time
)
SELECT 
    extract_date as new_date,
    CASE 
        WHEN extract_date IS NOT NULL THEN 'PROCESS_DATE'
        ELSE 'NO_NEW_DATA'
    END as action
FROM new_date
"""

CHECK_DUPLICATE_STORE_QUERY = """
SELECT name, city
FROM `{project_id}.{bronze_dataset_id}`.family_mart
WHERE name is not null
and extract_date = '{target_date}'
GROUP BY name, city
HAVING COUNT(*) > 1
"""

PROCESS_DUPLICATE_STORE_STEP1_LIST_DUPLICATE_STORES = """
CREATE OR REPLACE TABLE `{project_id}.{silver_dataset_id}.seven_eleven_step1_duplicate` AS
SELECT extract_date
       , name
       , city
       , district
       , address
       , long
       , lat
       , service 
       , CURRENT_TIMESTAMP() AS processed_at
FROM `{project_id}.{bronze_dataset_id}`.seven_eleven
WHERE extract_date = '{target_date}';
"""

PROCESS_DUPLICATE_STORE_STEP2_REMOVE_EXACT_DUPLICATE_STORES = """
CREATE OR REPLACE TABLE `{project_id}.{silver_dataset_id}.seven_eleven_step2_remove_exact_duplicate` AS
SELECT distinct extract_date
            , name
            , city
            , district
            , address
            , long
            , lat
            , service 
            , CURRENT_TIMESTAMP() AS processed_at
FROM `{project_id}.{silver_dataset_id}.seven_eleven_step1_duplicate`
WHERE extract_date = '{target_date}';
"""

PROCESS_DUPLICATE_STORE_STEP3_REMOVE_STORE_IN_SOUTH_DISTRICT_TAINAN = """
CREATE OR REPLACE TABLE `{project_id}.{silver_dataset_id}.seven_eleven_step3_remove_store_in_south_district_tainan` AS
select A.extract_date
       , A.name
       , A.city
       , A.district
       , A.address
       , A.long
       , A.lat
       , A.service
       , CURRENT_TIMESTAMP() AS processed_at
from `{project_id}.{silver_dataset_id}.seven_eleven_step2_remove_exact_duplicate` A
left join
(
  -- 安南店誤植到南區的店點清單
  select extract_date
         , name
         , city
         , district
         , address
         , long
         , lat
         , service
  from `{project_id}.{silver_dataset_id}.seven_eleven_step2_remove_exact_duplicate`
  where extract_date = '{target_date}'
  and district = '南區'
  and name in
  (
    select name
    from `{project_id}.{silver_dataset_id}.seven_eleven_step2_remove_exact_duplicate`
    where extract_date = '{target_date}'
    and district = '安南區'
  )
) B on A.extract_date = B.extract_date 
and A.name = B.name 
and A.city = B.city 
and A.district = B.district
and A.long = B.long
and A.lat = B.lat
and A.address = B.address
and A.service = B.service
where B.name is null
and A.extract_date ='{target_date}'
"""

PROCESS_DUPLICATE_STORE_STEP4_REMOVE_SHORTER_SERVICE_STORE = """
CREATE OR REPLACE TABLE `{project_id}.{silver_dataset_id}.seven_eleven_step4_remove_shorter_service_store` AS
  WITH  duplicate_store_name AS 
  (
    select extract_date, name
    from
    (
      SELECT extract_date
            , name
            , row_number() over(partition by name, extract_date order by extract_date desc, name) rn
      FROM `{project_id}.{silver_dataset_id}.seven_eleven_step3_remove_store_in_south_district_tainan`
      where name <> '鳳儀'
    ) A
    where rn > 1
  )
  ,duplicate_store AS
  (
    select extract_date, name
    from
    (
      select extract_date, name
            , row_number() over(partition by extract_date, name, city, district order by extract_date) rn
      from
      (
        select distinct A.extract_date
              , A.name
              , A.city
              , A.district
              , A.address
              , A.long
              , A.lat
              , A.service 
        from `{project_id}.{silver_dataset_id}.seven_eleven_step3_remove_store_in_south_district_tainan` A
        inner join duplicate_store_name B
        on A.name = B.name and A.extract_date = B.extract_date
        where A.name not in ('鳳儀')
      ) X
    ) W
    where rn > 1
  )
  , duplicate_store_fulllist AS
  (
    select T.extract_date
            , T.name
            , T.city
            , T.district
            , T.address
            , T.long
            , T.lat
            , T.service 
            , row_number() over(partition by T.extract_date, T.name, T.city, T.district order by length(service) desc ) idx
    from `{project_id}.{silver_dataset_id}.seven_eleven_step3_remove_store_in_south_district_tainan` T
    inner join duplicate_store U on T.name = U.name and T.extract_date = U.extract_date
  )
  select X.extract_date
         , X.name
         , X.city
         , X.district
         , X.address
         , X.long
         , X.lat
         , X.service
         , CURRENT_TIMESTAMP() AS processed_at
  from `{project_id}.{silver_dataset_id}.seven_eleven_step3_remove_store_in_south_district_tainan` X
  left join
  ( select * from duplicate_store_fulllist where idx = 2 ) Y
  on X.extract_date = Y.extract_date 
  and X.name = Y.name
  and X.city = Y.city
  and X.district = Y.district
  and X.address = Y.address
  and X.long = Y.long
  and X.lat = Y.lat
  and X.service = Y.service
  WHERE Y.name is null; 
"""

INSERT_DATA_TO_SILVER_QUERY = """
INSERT INTO `{project_id}.{silver_dataset_id}.family_mart`
SELECT PARSE_DATE('%Y-%m-%d', extract_date) as extract_date
       , name
       , city
       , district
       , address
       , ST_GEOGPOINT(long, lat) as location
       , SPLIT(service, ',') as service
       , CURRENT_TIMESTAMP() AS processed_at
FROM `{project_id}.{silver_dataset_id}.seven_eleven_step4_remove_shorter_service_store`
"""