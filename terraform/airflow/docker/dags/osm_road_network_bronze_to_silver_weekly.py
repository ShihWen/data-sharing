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

import logging
logging.info("DAG file osm_road_network_bronze_to_silver_weekly.py parsed at startup.")

# Constants
GCP_PROJECT_ID = "{{ var.value.gcp_project_id }}"
SILVER_DATASET = "osm_silver"
SILVER_TABLE = "road_network"
STAGING_TABLE = "road_network_staging"
GEOFABRIK_TAIWAN_URL = "https://download.geofabrik.de/asia/taiwan-latest.osm.pbf"


def download_osm_data_to_gcs(**context):
    """
    Downloads the latest OSM PBF data for Taiwan from Geofabrik and uploads it to GCS.
    If the file for the execution date already exists, this task will be skipped.
    """
    execution_date = context["ds"]
    gcs_hook = GCSHook()
    bucket_name = Variable.get("gcs_data_lake_bucket")
    
    file_name = f"osm/bronze/pbf/taiwan-latest-{execution_date}.osm.pbf"

    # Check if the file already exists in GCS for this execution date
    if gcs_hook.exists(bucket_name=bucket_name, object_name=file_name):
        print(f"File {file_name} already exists in GCS. Skipping download.")
        context["ti"].xcom_push(key="gcs_object_path", value=file_name)
        return

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
    Downloads the PBF file from GCS, processes it into a DataFrame using a
    boundary from the reference.dim_cities table, and uploads it to a 
    staging table in BigQuery.
    """
    gcs_object_path = context["ti"].xcom_pull(task_ids="download_osm_data", key="gcs_object_path")
    gcs_hook = GCSHook()
    bq_hook = BigQueryHook(use_legacy_sql=False)
    credentials = bq_hook.get_credentials()
    bucket_name = Variable.get("gcs_data_lake_bucket")
    project_id = Variable.get("gcp_project_id")
    
    # For now, we hardcode Taipei City. This can be parameterized later.
    clip_city_name_en = "Taipei"

    logging.info(f"Fetching boundary for '{clip_city_name_en}' from reference.dim_cities...")
    
    boundary_query = f"""
        SELECT ST_ASTEXT(geometry) as wkt
        FROM `{project_id}.reference.dim_cities`
        WHERE city_name_en = '{clip_city_name_en}' AND is_current = TRUE
        LIMIT 1
    """

    df_boundary = bq_hook.get_pandas_df(sql=boundary_query, dialect="standard")

    if df_boundary.empty:
        raise ValueError(f"Could not find a current boundary for city: {clip_city_name_en}")

    boundary_wkt = df_boundary['wkt'][0]
    logging.info("Boundary successfully fetched from BigQuery.")

    with tempfile.TemporaryDirectory() as tmpdir:
        local_file_path = Path(tmpdir) / "data.osm.pbf"
        
        logging.info(f"Downloading {gcs_object_path} from GCS to {local_file_path}...")
        gcs_hook.download(
            bucket_name=bucket_name,
            object_name=gcs_object_path,
            filename=str(local_file_path),
        )
        
        logging.info("Processing PBF file into DataFrame...")
        df = process_pbf_to_dataframe(
            pbf_file_path=str(local_file_path),
            boundary_wkt=boundary_wkt
        )
        
        if df.empty:
            logging.info("Skipping upload to BigQuery as the DataFrame is empty.")
            return

        logging.info(f"Uploading {len(df)} records to staging table: {project_id}.{SILVER_DATASET}.{STAGING_TABLE}")
        
        df.to_gbq(
            destination_table=f"{SILVER_DATASET}.{STAGING_TABLE}",
            project_id=project_id,
            credentials=credentials,
            if_exists='replace',
            table_schema=[
                {'name': 'osmid', 'type': 'INTEGER'},
                {'name': 'highway', 'type': 'STRING'},
                {'name': 'name', 'type': 'STRING'},
                {'name': 'lanes', 'type': 'INTEGER'},
                {'name': 'oneway', 'type': 'BOOLEAN'},
                {'name': 'reversed', 'type': 'BOOLEAN'},
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
        logging.info("Upload to staging table complete.")


with DAG(
    dag_id="osm_road_network_bronze_to_silver_weekly",
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    schedule="0 2 * * 6",  # Saturday at 10:00 AM
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
                    project_id="{{ var.value.gcp_project_id }}",
                    dataset_id=SILVER_DATASET,
                    table_id=SILVER_TABLE,
                    staging_table_id=STAGING_TABLE,
                ),
                "useLegacySql": False,
            }
        },
    )

    download_osm_data >> process_and_load_to_staging >> merge_into_silver_scd2 