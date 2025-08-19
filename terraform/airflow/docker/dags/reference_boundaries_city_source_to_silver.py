from __future__ import annotations

import pendulum
import json

from airflow.models.dag import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.hooks.gcs import GCSHook
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator

from utils.boundary_processing import process_city_boundaries
from utils.tdx_api import get_tdx_data
from sql.boundary_queries import MERGE_SCD2_CITIES, INSERT_UPDATED_CITIES


def fetch_and_save_boundaries_to_gcs(**context):
    """
    Fetches city, district, and village boundaries from the TDX API
    and saves the raw JSON to GCS (Bronze layer).
    """
    execution_date = context["ds"]
    bucket_name = Variable.get("gcs_data_lake_bucket")
    gcs_hook = GCSHook()
    
    # Fetch TDX credentials from Airflow Variables (which should be stored in Secret Manager)
    app_id = Variable.get("tdx_client_id")
    app_key = Variable.get("tdx_client_secret")
    auth_url = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
    
    urls = {
        "city": "https://tdx.transportdata.tw/api/basic/V3/Map/District/Boundary/City?%24format=GEOJSON",
    }
    
    gcs_paths = {}
    for level, url in urls.items():
        print(f"Fetching {level} boundaries from real TDX API...")
        data = get_tdx_data(app_id, app_key, auth_url, url)
        
        file_name = f"reference/bronze/boundaries/{level}_{execution_date}.json"
        gcs_hook.upload(
            bucket_name=bucket_name,
            object_name=file_name,
            data=json.dumps(data, ensure_ascii=False)
        )
        print(f"Saved raw {level} data to gs://{bucket_name}/{file_name}")
        gcs_paths[level] = file_name
    
    context["ti"].xcom_push(key="gcs_paths", value=gcs_paths)


def process_boundaries_to_staging(**context):
    """
    Reads the raw city boundary JSON file from GCS, transforms it,
    and loads it into a staging table in the reference dataset.
    """
    gcs_paths = context["ti"].xcom_pull(task_ids="fetch_and_save_boundaries_to_gcs", key="gcs_paths")
    city_gcs_path = gcs_paths.get("city")
    
    if not city_gcs_path:
        raise ValueError("GCS path for city boundaries not found in XComs.")

    gcs_hook = GCSHook()
    bq_hook = BigQueryHook()
    credentials = bq_hook.get_credentials()
    bucket_name = Variable.get("gcs_data_lake_bucket")
    project_id = Variable.get("gcp_project_id")

    print(f"Downloading city boundaries from gs://{bucket_name}/{city_gcs_path}")
    raw_data = gcs_hook.download_as_byte_array(
        bucket_name=bucket_name,
        object_name=city_gcs_path,
    ).decode('utf-8')
    
    print("Transforming city boundaries...")
    gdf = process_city_boundaries(raw_data)

    if gdf.empty:
        print("No city data to upload. Skipping.")
        return

    print(f"Uploading {len(gdf)} records to reference.dim_cities_staging...")
    gdf.to_gbq(
        destination_table="reference.dim_cities_staging",
        project_id=project_id,
        credentials=credentials,
        if_exists='replace',
        table_schema=[
            {'name': 'city_name_en', 'type': 'STRING'},
            {'name': 'city_name_zh', 'type': 'STRING'},
            {'name': 'update_date', 'type': 'TIMESTAMP'},
            {'name': 'check_date', 'type': 'TIMESTAMP'},
            {'name': 'geometry', 'type': 'GEOGRAPHY'},
        ]
    )
    print("Successfully loaded data into reference.dim_cities_staging.")

with DAG(
    dag_id="reference_boundaries_city_source_to_silver",
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    schedule="@yearly",
    catchup=False,
    tags=["reference", "silver", "dimensions", "city"],
    default_args={
        "owner": "data_engineering",
        "retries": 1,
        "retry_delay": pendulum.duration(minutes=5),
    },
) as dag:

    fetch_bronze_data = PythonOperator(
        task_id="fetch_and_save_boundaries_to_gcs",
        python_callable=fetch_and_save_boundaries_to_gcs,
    )

    process_silver_staging = PythonOperator(
        task_id="process_boundaries_to_staging",
        python_callable=process_boundaries_to_staging,
    )
    
    merge_into_silver_scd2 = BigQueryInsertJobOperator(
        task_id="merge_into_silver_scd2",
        configuration={
            "query": {
                "query": MERGE_SCD2_CITIES.format(
                    project_id="{{ var.value.gcp_project_id }}",
                    dataset_id="reference",
                    table_id="dim_cities",
                    staging_table_id="dim_cities_staging",
                ),
                "useLegacySql": False,
            }
        },
    )

    insert_updated_records = BigQueryInsertJobOperator(
        task_id="insert_updated_records",
        configuration={
            "query": {
                "query": INSERT_UPDATED_CITIES.format(
                    project_id="{{ var.value.gcp_project_id }}",
                    dataset_id="reference",
                    table_id="dim_cities",
                    staging_table_id="dim_cities_staging",
                ),
                "useLegacySql": False,
            }
        },
    )

    fetch_bronze_data >> process_silver_staging >> merge_into_silver_scd2 >> insert_updated_records 