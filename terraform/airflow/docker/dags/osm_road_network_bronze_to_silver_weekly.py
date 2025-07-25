from __future__ import annotations

import pendulum

from airflow.models.dag import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.providers.google.cloud.hooks.gcs import GCSHook

from sql.osm_road_network_queries import MERGE_SCD2_ROAD_NETWORK

# Constants
GCS_BUCKET = "{{ var.value.gcs_data_lake_bucket }}"
GCP_PROJECT_ID = "{{ var.value.gcp_project_id }}"
SILVER_DATASET = "osm_silver"
SILVER_TABLE = "road_network"
STAGING_TABLE = "road_network_staging"
GEOFABRIK_TAIWAN_URL = "https://download.geofabrik.de/asia/taiwan-latest.osm.pbf"


def download_osm_data_to_gcs(**context):
    """
    Downloads the latest OSM data for Taiwan from Geofabrik and uploads it to GCS.
    A real implementation would download diffs, but for this initial setup,
    we download the full file.
    """
    execution_date = context["ds"]
    gcs_hook = GCSHook()
    # In a real scenario, we would use a library like `requests` to download the file.
    # To keep this example simple, we'll simulate the download.
    # This function would need to be expanded with actual download logic.
    print(f"Simulating download of {GEOFABRIK_TAIWAN_URL} for execution date {execution_date}")
    
    # Placeholder for the downloaded file content
    dummy_content = b"dummy osm pbf data"
    file_name = f"osm/bronze/pbf/taiwan-latest-{execution_date}.osm.pbf"
    
    gcs_hook.upload(
        bucket_name=GCS_BUCKET,
        object_name=file_name,
        data=dummy_content,
    )
    
    context["ti"].xcom_push(key="gcs_object_path", value=file_name)
    print(f"Successfully uploaded to gs://{GCS_BUCKET}/{file_name}")


def process_osm_data_and_load_to_staging(**context):
    """
    This is a placeholder function.
    In a real implementation, this function would:
    1. Download the PBF file from GCS.
    2. Use a library like `pyosmium` to parse the file.
    3. For each road, perform a reverse geocode to get city/district if needed.
    4. Transform the data to match the BigQuery schema.
    5. Load the transformed data into the staging BigQuery table.
    """
    gcs_object_path = context["ti"].xcom_pull(task_ids="download_osm_data", key="gcs_object_path")
    print(f"Placeholder: Processing data from {gcs_object_path} and loading to staging table.")
    # Here you would implement the logic using pandas, pyosmium, etc.
    # and the BigQuery client library to load data to the staging table.
    print(f"Data loaded to BigQuery table: {GCP_PROJECT_ID}.{SILVER_DATASET}.{STAGING_TABLE}")


with DAG(
    dag_id="osm_road_network_bronze_to_silver_weekly",
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    schedule="0 10 * * 6",  # Saturday at 10:00 AM
    catchup=False,
    tags=["osm", "silver"],
    default_args={
        "owner": "data_engineering",
        "retries": 1,
        "retry_delay": pendulum.duration(minutes=5),
    },
) as dag:
    
    download_osm_data = PythonOperator(
        task_id="download_osm_data",
        python_callable=download_osm_data_to_gcs,
    )
    
    process_and_load_to_staging = PythonOperator(
        task_id="process_and_load_to_staging",
        python_callable=process_osm_data_and_load_to_staging,
    )

    merge_into_silver_scd2 = BigQueryInsertJobOperator(
        task_id="merge_into_silver_scd2",
        configuration={
            "query": {
                "query": MERGE_SCD2_ROAD_NETWORK.format(
                    project_id=GCP_PROJECT_ID,
                    dataset_id=SILVER_DATASET,
                    table_id=SILVER_TABLE,
                    staging_table_id=STAGING_TABLE,
                ),
                "useLegacySql": False,
            }
        },
    )

    download_osm_data >> process_and_load_to_staging >> merge_into_silver_scd2 