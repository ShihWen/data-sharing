from __future__ import annotations

import pendulum
import json
import time
import pandas as pd

from airflow.models.dag import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.hooks.gcs import GCSHook
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator

from utils.mrt_processing import process_mrt_shape
from utils.tdx_api import get_tdx_data
# from sql.bus_queries import MERGE_SCD2_CITY_BUS_ROUTE, INSERT_UPDATED_CITY_BUS_ROUTE

def fetch_mrt_shape_to_gcs(**context):
    """
    Fetches mrt shape from the TDX API and saves the raw JSON to GCS.
    """
    execution_year_month = context["ds"][:7]
    bucket_name = Variable.get("gcs_data_lake_bucket")
    gcs_hook = GCSHook()
    
    app_id = Variable.get("tdx_client_id")
    app_key = Variable.get("tdx_client_secret")
    auth_url = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
    system_dict = {
        "TRTC":"臺北捷運",
        "KRTC":"高雄捷運",
        "TYMC":"桃園捷運",
        "TMRT":"臺中捷運",
        "KLRT":"高雄輕軌",
        "NTDLRT":"淡海輕軌",
        "NTMC":"新北捷運",
        "TRTCMG":"貓空纜車",
        "NTALRT":"安坑輕軌",
    }
    for system_id, system_name in system_dict.items():
        url = f"https://tdx.transportdata.tw/api/basic/v2/Rail/Metro/Shape/{system_id}?%24format=JSON"
    
        file_name = f"bus/bronze/mrt_shape/mrt_shape_{system_id}_{execution_year_month}.json"

        # Check if the file already exists in GCS for this execution date
        if gcs_hook.exists(bucket_name=bucket_name, object_name=file_name):
            print(f"File {file_name} already exists in GCS. Skipping download.")
            print("--------------------------------")
        else:
            print(f"Fetching mrt shape from {system_id} TDX API...")
            data = get_tdx_data(app_id, app_key, auth_url, url)

            gcs_hook.upload(
                bucket_name=bucket_name,
                object_name=file_name,
                data=json.dumps(data, ensure_ascii=False)
            )
            print(f"Saved raw mrt shape data to gs://{bucket_name}/{file_name}")
            print("Waiting for 15 seconds before fetching next city...")
            time.sleep(15)
            print("--------------------------------")
        # Ensure XCom is pushed exactly once at the end of the task
        print(f"Pushed XCom for {system_id} mrt shape data to GCS.")
        context["ti"].xcom_push(key=f"gcs_path_{system_id}", value=file_name)


    print("Finished fetching mrt shape data to GCS.")


def process_mrt_shape_to_staging(**context):
    """
    Reads the raw mrt shape JSON file from GCS, transforms it,
    and loads it into a staging table in the reference dataset.
    """
    system_dict = {
        "TRTC":"臺北捷運",
        "KRTC":"高雄捷運",
        "TYMC":"桃園捷運",
        "TMRT":"臺中捷運",
        "KLRT":"高雄輕軌",
        "NTDLRT":"淡海輕軌",
        "NTMC":"新北捷運",
        "TRTCMG":"貓空纜車",
        "NTALRT":"安坑輕軌",
    }


    gcs_hook = GCSHook()
    bq_hook = BigQueryHook()
    credentials = bq_hook.get_credentials()
    bucket_name = Variable.get("gcs_data_lake_bucket")
    project_id = Variable.get("gcp_project_id")

    gdfs = []
    for system_id, system_name in system_dict.items():
        gcs_path = context["ti"].xcom_pull(task_ids="fetch_mrt_shape_to_gcs", key=f"gcs_path_{system_id}")
        
        if not gcs_path:
            raise ValueError(f"GCS path for mrt shape {system_id} not found in XComs.")

        print(f"Downloading mrt shape from gs://{bucket_name}/{gcs_path}")
        print(f"Retrieved GCS path from XCom: {gcs_path}")
        raw_data = gcs_hook.download_as_byte_array(
            bucket_name=bucket_name,
            object_name=gcs_path,
        ).decode('utf-8')
        
        print("Transforming mrt shape...")
        gdf = process_mrt_shape(raw_data)

        if gdf.empty:
            print("No mrt shape data to upload. Skipping.")
            return

        print(f"Uploading {len(gdf)} records to railway_silver.mrt_shape_staging...")

        # Explicitly cast string columns to object (string) type
        string_columns = [
            "line_no", "line_id", "line_name_zh_tw", "line_name_en","UpdateTime"
        ]
        for col in string_columns:
            if col in gdf.columns:
                gdf[col] = gdf[col].astype(str)

        gdf['system_id'] = system_id
        gdf['system_name'] = system_name
        gdfs.append(gdf)

    gdf = pd.concat(gdfs)

    gdf.to_gbq(
        destination_table="railway_silver.mrt_shape_staging",
        project_id=project_id,
        credentials=credentials,
        if_exists='replace',
        table_schema=[
            {'name': 'line_no', 'type': 'STRING'},
            {'name': 'line_id', 'type': 'STRING'},
            {'name': 'line_name_zh_tw', 'type': 'STRING'},
            {'name': 'line_name_en', 'type': 'STRING'},
            {'name': 'UpdateTime', 'type': 'STRING'},
            {'name': 'geometry', 'type': 'GEOGRAPHY'},
            {'name': 'system_id', 'type': 'STRING'},
            {'name': 'system_name', 'type': 'STRING'}
        ]
    )
    print("Successfully loaded data into city_bus_shape_staging.")

with DAG(
    dag_id="tdx_mrt_shape_source_to_silver",
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    schedule="@monthly",
    catchup=False,
    tags=["railway", "silver", "tdx", "mrt_shape"],
    default_args={
        "owner": "data_engineering",
        "retries": 1,
        "retry_delay": pendulum.duration(minutes=5),
    },
) as dag:

    fetch_bronze_data = PythonOperator(
        task_id="fetch_mrt_shape_to_gcs",
        python_callable=fetch_mrt_shape_to_gcs,
    )

    process_silver_staging = PythonOperator(
        task_id="process_mrt_shape_to_staging",
        python_callable=process_mrt_shape_to_staging,
    )
    
    # merge_into_silver_scd2 = BigQueryInsertJobOperator(
    #     task_id="merge_into_silver_scd2",
    #     configuration={
    #         "query": {
    #             "query": MERGE_SCD2_CITY_BUS_ROUTE.format(
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
    #             "query": INSERT_UPDATED_CITY_BUS_ROUTE.format(
    #                 project_id="{{ var.value.gcp_project_id }}",
    #                 dataset_id="bus_silver",
    #                 table_id="city_bus_shape",
    #                 staging_table_id="city_bus_shape_staging",
    #             ),
    #             "useLegacySql": False,
    #         }
    #     },
    # )

    fetch_bronze_data >> process_silver_staging #>> merge_into_silver_scd2 >> insert_updated_records 