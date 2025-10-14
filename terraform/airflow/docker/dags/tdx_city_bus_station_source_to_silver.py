from __future__ import annotations

import pendulum
import json
import pandas as pd

from airflow.models.dag import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.hooks.gcs import GCSHook
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator

from utils.bus_processing import process_inter_city_bus_station
from utils.tdx_api import get_tdx_data
from sql.bus_queries import MERGE_SCD2_INTERCITY_BUS_ROUTE, INSERT_UPDATED_INTERCITY_BUS_ROUTE, MERGE_SCD2_INTERCITY_BUS_STATION, INSERT_UPDATED_INTERCITY_BUS_STATION

def fetch_bus_station_to_gcs(**context):
    """
    Fetches city bus shape from the TDX API and saves the raw JSON to GCS.
    """
    execution_year_month = context["ds"][:7]
    bucket_name = Variable.get("gcs_data_lake_bucket")
    gcs_hook = GCSHook()
    
    app_id = Variable.get("tdx_client_id")
    app_key = Variable.get("tdx_client_secret")
    auth_url = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
    
    city_list = ["Taipei", "NewTaipei", "Taoyuan", "Taichung", "Tainan", 
                 "Kaohsiung", "Keelung", "Hsinchu", "HsinchuCounty", "MiaoliCounty",
                  "ChanghuaCounty", "NantouCounty", "YunlinCounty", "ChiayiCounty", "Chiayi", 
                  "PingtungCounty", "YilanCounty", "HualienCounty", "TaitungCounty", "KinmenCounty", 
                  "PenghuCounty"]
    for city in city_list:
        url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/Station/City/{city}?%24format=JSON"
        file_name = f"bus/bronze/city_bus_station/city_bus_station_{city}_{execution_year_month}.json"

        # Check if the file already exists in GCS for this execution date
        if gcs_hook.exists(bucket_name=bucket_name, object_name=file_name):
            print(f"File {file_name} already exists in GCS. Skipping download.")
            print("--------------------------------")
        else:
            print("Fetching bus station from real TDX API...")
            data = get_tdx_data(app_id, app_key, auth_url, url)   
            print(f"Saved raw bus station data to gs://{bucket_name}/{file_name}")
            print("Waiting for 15 seconds before fetching next city...")
            time.sleep(15)
            print("--------------------------------")
            gcs_hook.upload(
                bucket_name=bucket_name,
                object_name=file_name,
                data=json.dumps(data, ensure_ascii=False)
            )
            print(f"Saved raw bus station data to gs://{bucket_name}/{file_name}")
        
        # Ensure XCom is pushed exactly once at the end of the task
        context["ti"].xcom_push(key=f"gcs_path_{city}", value=file_name)

def process_bus_station_to_staging(**context):
    """
    Reads the raw bus station JSON file from GCS, transforms it,
    and loads it into a staging table in the reference dataset.
    """
    city_list = ["Taipei", "NewTaipei", "Taoyuan", "Taichung", "Tainan", 
                 "Kaohsiung", "Keelung", "Hsinchu", "HsinchuCounty", "MiaoliCounty",
                  "ChanghuaCounty", "NantouCounty", "YunlinCounty", "ChiayiCounty", "Chiayi", 
                  "PingtungCounty", "YilanCounty", "HualienCounty", "TaitungCounty", "KinmenCounty", 
                  "PenghuCounty"]

    gcs_hook = GCSHook()
    bq_hook = BigQueryHook()
    credentials = bq_hook.get_credentials()
    bucket_name = Variable.get("gcs_data_lake_bucket")
    project_id = Variable.get("gcp_project_id")

    gdfs = []
    for city in city_list:
        gcs_path = context["ti"].xcom_pull(task_ids="fetch_bus_shape_to_gcs", key=f"gcs_path_{city}")
        
        if not gcs_path:
            raise ValueError(f"GCS path for bus shape {city} not found in XComs.")

        print(f"Downloading bus station from gs://{bucket_name}/{gcs_path}")
        print(f"Retrieved GCS path from XCom: {gcs_path}")
        raw_data = gcs_hook.download_as_byte_array(
            bucket_name=bucket_name,
            object_name=gcs_path,
        ).decode('utf-8')
        
        print("Transforming bus station...")
        gdf = process_inter_city_bus_station(raw_data)


        if gdf.empty:
            print("No bus station data to upload. Skipping.")
            return

        print(f"Uploading {len(gdf)} records to bus_silver.inter_city_bus_station_staging...")

        # Ensure pandas GeoDataFrame types are correctly mapped to BigQuery types
        # For string columns, ensure they are explicitly converted to string type
        string_columns = [
            'station_uid',
            'station_id',
            'station_group_id',
            'station_address',
            'location_city_code',
            'bearing',
            'geometry',
        ]
        for col in string_columns:
            if col in gdf.columns:
                gdf[col] = gdf[col].astype(str)
                # Replace 'None' strings with actual None values if they exist after conversion
                gdf[col] = gdf[col].replace('None', None)

        # Convert version_id to integer if it exists
        if 'version_id' in gdf.columns:
            gdf['version_id'] = pd.to_numeric(gdf['version_id'], errors='coerce').astype('Int64')
        
        # Convert update_time to datetime objects
        if 'update_time' in gdf.columns:
            gdf['update_time'] = pd.to_datetime(gdf['update_time'], errors='coerce')
                
        gdf['city'] = city
        gdfs.append(gdf)

    gdf = pd.concat(gdfs)
    # Define BigQuery schema for the staging table, including nested and repeated fields
    table_schema = [
        {'name': 'station_uid', 'type': 'STRING', 'mode': 'REQUIRED'},
        {'name': 'station_id', 'type': 'STRING', 'mode': 'REQUIRED'},
        {'name': 'station_name', 'type': 'RECORD', 'mode': 'REQUIRED', 'fields': [
            {'name': 'zh_tw', 'type': 'STRING', 'mode': 'REQUIRED'},
            {'name': 'en', 'type': 'STRING', 'mode': 'NULLABLE'},
        ]},
        {'name': 'station_position', 'type': 'RECORD', 'mode': 'REQUIRED', 'fields': [
            {'name': 'position_lon', 'type': 'FLOAT', 'mode': 'REQUIRED'},
            {'name': 'position_lat', 'type': 'FLOAT', 'mode': 'REQUIRED'},
            {'name': 'geohash', 'type': 'STRING', 'mode': 'NULLABLE'},
        ]},
        {'name': 'station_group_id', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'stops', 'type': 'RECORD', 'mode': 'REPEATED', 'fields': [
            {'name': 'stop_uid', 'type': 'STRING', 'mode': 'REQUIRED'},
            {'name': 'stop_id', 'type': 'STRING', 'mode': 'REQUIRED'},
            {'name': 'stop_name', 'type': 'RECORD', 'mode': 'REQUIRED', 'fields': [
                {'name': 'zh_tw', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'en', 'type': 'STRING', 'mode': 'NULLABLE'},
            ]},
            {'name': 'route_uid', 'type': 'STRING', 'mode': 'REQUIRED'},
            {'name': 'route_id', 'type': 'STRING', 'mode': 'REQUIRED'},
            {'name': 'route_name', 'type': 'RECORD', 'mode': 'REQUIRED', 'fields': [
                {'name': 'zh_tw', 'type': 'STRING', 'mode': 'REQUIRED'},
                {'name': 'en', 'type': 'STRING', 'mode': 'NULLABLE'},
            ]},
        ]},
        {'name': 'location_city_code', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'bearing', 'type': 'STRING', 'mode': 'NULLABLE'},
        {'name': 'update_time', 'type': 'TIMESTAMP', 'mode': 'NULLABLE'},
        {'name': 'version_id', 'type': 'INTEGER', 'mode': 'NULLABLE'},
        {'name': 'geometry', 'type': 'GEOGRAPHY', 'mode': 'NULLABLE'},
    ]
        
    gdf.to_gbq(
        destination_table="bus_silver.city_bus_station_staging",
        project_id=project_id,
        credentials=credentials,
        if_exists='replace',
        table_schema=table_schema # Use the defined schema
    )
    print("Successfully loaded data into bus_silver.city_bus_station_staging.")

with DAG(
    dag_id="tdx_intercity_bus_station_source_to_silver",
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    schedule="@monthly",
    catchup=False,
    tags=["bus", "silver", "tdx", "inter_city_bus_station"],
    default_args={
        "owner": "data_engineering",
        "retries": 1,
        "retry_delay": pendulum.duration(minutes=5),
    },
) as dag:

    fetch_bronze_data = PythonOperator(
        task_id="fetch_bus_station_to_gcs",
        python_callable=fetch_bus_station_to_gcs,
    )

    process_silver_staging = PythonOperator(
        task_id="process_bus_station_to_staging",
        python_callable=process_bus_station_to_staging,
    )
    
    # merge_into_silver_scd2 = BigQueryInsertJobOperator(
    #     task_id="merge_into_silver_scd2",
    #     configuration={
    #         "query": {
    #             "query": MERGE_SCD2_INTERCITY_BUS_STATION.format(
    #                 project_id="{{ var.value.gcp_project_id }}",
    #                 dataset_id="bus_silver",
    #                 table_id="inter_city_bus_station",
    #                 staging_table_id="inter_city_bus_station_staging",
    #             ),
    #             "useLegacySql": False,
    #         }
    #     },
    # )

    # insert_updated_records = BigQueryInsertJobOperator(
    #     task_id="insert_updated_records",
    #     configuration={
    #         "query": {
    #             "query": INSERT_UPDATED_INTERCITY_BUS_STATION.format(
    #                 project_id="{{ var.value.gcp_project_id }}",
    #                 dataset_id="bus_silver",
    #                 table_id="inter_city_bus_station",
    #                 staging_table_id="inter_city_bus_station_staging",
    #             ),
    #             "useLegacySql": False,
    #         }
    #     },
    # )

    fetch_bronze_data >> process_silver_staging #>> merge_into_silver_scd2 >> insert_updated_records 