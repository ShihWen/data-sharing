from __future__ import annotations

import pendulum
import json
import time

from airflow.models.dag import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.hooks.gcs import GCSHook
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator

from utils.bus_processing import process_inter_city_bus_shape
from utils.tdx_api import get_tdx_data
from sql.bus_queries import MERGE_SCD2_INTERCITY_BUS_ROUTE, INSERT_UPDATED_INTERCITY_BUS_ROUTE

def fetch_bus_shape_to_gcs(**context):
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
        url = f"https://tdx.transportdata.tw/api/basic/v2/Bus/Shape/City/{city}?%24format=JSON"
    
        print(f"Fetching bus shape from {city} TDX API...")
        data = get_tdx_data(app_id, app_key, auth_url, url)
    
        file_name = f"bus/bronze/city_bus_shape/city_bus_shape_{city}_{execution_year_month}.json"

        # Check if the file already exists in GCS for this execution date
        if gcs_hook.exists(bucket_name=bucket_name, object_name=file_name):
            print(f"File {file_name} already exists in GCS. Skipping download.")
        else:
            gcs_hook.upload(
                bucket_name=bucket_name,
                object_name=file_name,
                data=json.dumps(data, ensure_ascii=False)
            )
            print(f"Saved raw bus shape data to gs://{bucket_name}/{file_name}")
    
        # Ensure XCom is pushed exactly once at the end of the task
        context["ti"].xcom_push(key=f"gcs_path_{city}", value=file_name)

        print(f"Pushed XCom for {city} bus shape data to GCS.")
        print("Waiting for 15 seconds before fetching next city...")
        time.sleep(15)
        print("--------------------------------")
    print("Finished fetching bus shape data to GCS.")


def process_bus_shape_to_staging(**context):
    """
    Reads the raw bus shape JSON file from GCS, transforms it,
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

        print(f"Downloading bus shape from gs://{bucket_name}/{gcs_path}")
        print(f"Retrieved GCS path from XCom: {gcs_path}")
        raw_data = gcs_hook.download_as_byte_array(
            bucket_name=bucket_name,
            object_name=gcs_path,
        ).decode('utf-8')
        
        print("Transforming bus shape...")
        gdf = process_inter_city_bus_shape(raw_data)

        if gdf.empty:
            print("No bus shape data to upload. Skipping.")
            return

        print(f"Uploading {len(gdf)} records to reference.dim_inter_city_bus_shape_staging...")

        # Explicitly cast string columns to object (string) type
        string_columns = [
            "route_uid", "route_id", "route_name_zh_tw", "route_name_en",
            "sub_route_uid", "sub_route_id", "sub_route_name_zh_tw", "sub_route_name_en",
            "update_time", "direction", "version_id"
        ]
        for col in string_columns:
            if col in gdf.columns:
                gdf[col] = gdf[col].astype(str)

        gdf['city'] = city
        gdfs.append(gdf)

    gdf = pd.concat(gdfs)

    gdf.to_gbq(
        destination_table="bus_silver.city_bus_shape_staging",
        project_id=project_id,
        credentials=credentials,
        if_exists='replace',
        table_schema=[
            {'name': 'route_uid', 'type': 'STRING'},
            {'name': 'route_id', 'type': 'STRING'},
            {'name': 'route_name_zh_tw', 'type': 'STRING'},
            {'name': 'route_name_en', 'type': 'STRING'},
            {'name': 'sub_route_uid', 'type': 'STRING'},
            {'name': 'sub_route_id', 'type': 'STRING'},
            {'name': 'sub_route_name_zh_tw', 'type': 'STRING'},
            {'name': 'sub_route_name_en', 'type': 'STRING'},
            {'name': 'direction', 'type': 'STRING'},
            {'name': 'update_time', 'type': 'STRING'},
            {'name': 'version_id', 'type': 'STRING'},
            {'name': 'geometry', 'type': 'GEOGRAPHY'},
            {'name': 'city', 'type': 'STRING'}
        ]
    )
    print("Successfully loaded data into city_bus_shape_staging.")

with DAG(
    dag_id="tdx_city_bus_shape_source_to_silver",
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    schedule="@monthly",
    catchup=False,
    tags=["bus", "silver", "tdx", "city_bus_shape"],
    default_args={
        "owner": "data_engineering",
        "retries": 1,
        "retry_delay": pendulum.duration(minutes=5),
    },
) as dag:

    fetch_bronze_data = PythonOperator(
        task_id="fetch_bus_shape_to_gcs",
        python_callable=fetch_bus_shape_to_gcs,
    )

    process_silver_staging = PythonOperator(
        task_id="process_bus_shape_to_staging",
        python_callable=process_bus_shape_to_staging,
    )
    
    # merge_into_silver_scd2 = BigQueryInsertJobOperator(
    #     task_id="merge_into_silver_scd2",
    #     configuration={
    #         "query": {
    #             "query": MERGE_SCD2_INTERCITY_BUS_ROUTE.format(
    #                 project_id="{{ var.value.gcp_project_id }}",
    #                 dataset_id="bus_silver",
    #                 table_id="city_bus_shape",
    #                 staging_table_id="city_bus_shape_staging",
    #             ),
    #             "useLegacySql": False,
    #         }
    #     },
    # )

    # insert_updated_records = BigQueryInsertJobOperator(
    #     task_id="insert_updated_records",
    #     configuration={
    #         "query": {
    #             "query": INSERT_UPDATED_INTERCITY_BUS_ROUTE.format(
    #                 project_id="{{ var.value.gcp_project_id }}",
    #                 dataset_id="bus_silver",
    #                 table_id="inter_city_bus_shape",
    #                 staging_table_id="inter_city_bus_shape_staging",
    #             ),
    #             "useLegacySql": False,
    #         }
    #     },
    # )

    fetch_bronze_data >> process_silver_staging #>> merge_into_silver_scd2 >> insert_updated_records 