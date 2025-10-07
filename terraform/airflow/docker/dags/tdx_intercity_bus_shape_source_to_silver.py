from __future__ import annotations

import pendulum
import json

from airflow.models.dag import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.hooks.gcs import GCSHook
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator

from utils.bus_processing import process_inter_city_bus_shape
from utils.tdx_api import get_tdx_data
from sql.boundary_queries import MERGE_SCD2_TOWNS, INSERT_UPDATED_TOWNS

def fetch_bus_shape_to_gcs(**context):
    """
    Fetches intercity bus shape from the TDX API and saves the raw JSON to GCS.
    """
    execution_year_month = context["ds"][:7]
    bucket_name = Variable.get("gcs_data_lake_bucket")
    gcs_hook = GCSHook()
    
    app_id = Variable.get("tdx_client_id")
    app_key = Variable.get("tdx_client_secret")
    auth_url = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
    
    url = "https://tdx.transportdata.tw/api/basic/v2/Bus/Shape/InterCity?%24format=JSON"
    
    print("Fetching bus shape from real TDX API...")
    data = get_tdx_data(app_id, app_key, auth_url, url)
    
    file_name = f"bus/bronze/inter_city_bus_shape/inter_city_bus_shape_{execution_year_month}.json"

    # Check if the file already exists in GCS for this execution date
    if gcs_hook.exists(bucket_name=bucket_name, object_name=file_name):
        print(f"File {file_name} already exists in GCS. Skipping download.")
        context["ti"].xcom_push(key="gcs_object_path", value=file_name)
        return

    gcs_hook.upload(
        bucket_name=bucket_name,
        object_name=file_name,
        data=json.dumps(data, ensure_ascii=False)
    )
    print(f"Saved raw bus shape data to gs://{bucket_name}/{file_name}")
    context["ti"].xcom_push(key="gcs_path", value=file_name)

def process_bus_shape_to_staging(**context):
    """
    Reads the raw bus shape JSON file from GCS, transforms it,
    and loads it into a staging table in the reference dataset.
    """
    gcs_path = context["ti"].xcom_pull(task_ids="fetch_bus_shape_to_gcs", key="gcs_path")
    
    if not gcs_path:
        raise ValueError("GCS path for bus shape not found in XComs.")

    gcs_hook = GCSHook()
    bq_hook = BigQueryHook()
    credentials = bq_hook.get_credentials()
    bucket_name = Variable.get("gcs_data_lake_bucket")
    project_id = Variable.get("gcp_project_id")

    print(f"Downloading bus shape from gs://{bucket_name}/{gcs_path}")
    raw_data = gcs_hook.download_as_byte_array(
        bucket_name=bucket_name,
        object_name=gcs_path,
    ).decode('utf-8')
    
    print("Transforming bus shape...")
    gdf = process_inter_city_bus_shape(raw_data)
    print("--------------------------------")
    print(gdf.info())    

    if gdf.empty:
        print("No bus shape data to upload. Skipping.")
        return

    print(f"Uploading {len(gdf)} records to reference.dim_inter_city_bus_shape_staging...")
    gdf.to_gbq(
        destination_table="reference.dim_inter_city_bus_shape_staging",
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
        ]
    )
    print("Successfully loaded data into reference.dim_inter_city_bus_shape_staging.")

with DAG(
    dag_id="tdx_intercity_bus_shape_source_to_silver",
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    schedule="@yearly",
    catchup=False,
    tags=["reference", "silver", "dimensions", "town"],
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
    #             "query": MERGE_SCD2_TOWNS.format(
    #                 project_id="{{ var.value.gcp_project_id }}",
    #                 dataset_id="reference",
    #             ),
    #             "useLegacySql": False,
    #         }
    #     },
    # )

    # insert_updated_records = BigQueryInsertJobOperator(
    #     task_id="insert_updated_records",
    #     configuration={
    #         "query": {
    #             "query": INSERT_UPDATED_TOWNS.format(
    #                 project_id="{{ var.value.gcp_project_id }}",
    #                 dataset_id="reference",
    #             ),
    #             "useLegacySql": False,
    #         }
    #     },
    # )

    fetch_bronze_data >> process_silver_staging # >> merge_into_silver_scd2 >> insert_updated_records 