from __future__ import annotations

import pendulum
import requests
from pathlib import Path
import tempfile

from airflow.models.dag import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.providers.google.cloud.hooks.gcs import GCSHook
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook

from sql.osm_road_network_queries import MERGE_SCD2_ROAD_NETWORK
from utils.osm_processing import process_pbf_to_dataframe

# Constants
GCP_PROJECT_ID = "{{ var.value.gcp_project_id }}"
SILVER_DATASET = "osm_silver"
SILVER_TABLE = "road_network"
STAGING_TABLE = "road_network_staging"
GEOFABRIK_TAIWAN_URL = "https://download.geofabrik.de/asia/taiwan-latest.osm.pbf"


def download_osm_data_to_gcs(**context):
    """
    Downloads the latest OSM PBF data for Taiwan from Geofabrik and uploads it to GCS.
    """
    execution_date = context["ds"]
    gcs_hook = GCSHook()
    bucket_name = Variable.get("gcs_data_lake_bucket")
    
    file_name = f"osm/bronze/pbf/taiwan-latest-{execution_date}.osm.pbf"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        local_file_path = Path(tmpdir) / "taiwan-latest.osm.pbf"
        
        print(f"Downloading data from {GEOFABRIK_TAIWAN_URL} to {local_file_path}")
        
        try:
            with requests.get(GEOFABRIK_TAIWAN_URL, stream=True) as r:
                r.raise_for_status()
                with open(local_file_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            
            print("Download complete. Uploading to GCS...")
            
            gcs_hook.upload(
                bucket_name=bucket_name,
                object_name=file_name,
                filename=str(local_file_path),
            )
            
            context["ti"].xcom_push(key="gcs_object_path", value=file_name)
            print(f"Successfully uploaded to gs://{bucket_name}/{file_name}")

        except requests.exceptions.RequestException as e:
            print(f"Error downloading file: {e}")
            raise


def process_osm_data_and_load_to_staging(**context):
    """
    Downloads the PBF file from GCS, processes it into a DataFrame,
    and uploads it to a staging table in BigQuery.
    """
    gcs_object_path = context["ti"].xcom_pull(task_ids="download_osm_data", key="gcs_object_path")
    gcs_hook = GCSHook()
    bq_hook = BigQueryHook()
    credentials = bq_hook.get_credentials()
    bucket_name = Variable.get("gcs_data_lake_bucket")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        local_file_path = Path(tmpdir) / "data.osm.pbf"
        
        print(f"Downloading {gcs_object_path} from GCS to {local_file_path}...")
        gcs_hook.download(
            bucket_name=bucket_name,
            object_name=gcs_object_path,
            filename=str(local_file_path),
        )
        
        print("Processing PBF file into DataFrame...")
        df = process_pbf_to_dataframe(str(local_file_path))
        
        print(f"Uploading {len(df)} records to staging table: {GCP_PROJECT_ID}.{SILVER_DATASET}.{STAGING_TABLE}")
        
        df.to_gbq(
            destination_table=f"{SILVER_DATASET}.{STAGING_TABLE}",
            project_id=GCP_PROJECT_ID,
            credentials=credentials,
            if_exists='replace',
            table_schema=[
                {'name': 'osmid', 'type': 'INTEGER'},
                {'name': 'highway', 'type': 'STRING'},
                {'name': 'name', 'type': 'STRING'},
                {'name': 'lanes', 'type': 'INTEGER'},
                {'name': 'oneway', 'type': 'STRING'},
                {'name': 'reversed', 'type': 'STRING'},
                {'name': 'length', 'type': 'FLOAT'},
                {'name': 'bridge', 'type': 'STRING'},
                {'name': 'maxspeed', 'type': 'INTEGER'},
                {'name': 'ref', 'type': 'STRING'},
                {'name': 'service', 'type': 'STRING'},
                {'name': 'width', 'type': 'FLOAT'},
                {'name': 'access', 'type': 'STRING'},
                {'name': 'tunnel', 'type': 'STRING'},
                {'name': 'junction', 'type': 'STRING'},
                {'name': 'city', 'type': 'STRING'},
                {'name': 'district', 'type': 'STRING'},
                {'name': 'geometry', 'type': 'GEOGRAPHY'},
                {'name': 'u', 'type': 'INTEGER'},
                {'name': 'v', 'type': 'INTEGER'},
            ]
        )
        print("Upload to staging table complete.")


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