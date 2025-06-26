import os
from datetime import datetime, timedelta
from airflow.decorators import dag, task
from airflow.models import Variable
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator
import google.auth
import google.auth.transport.requests
from google.oauth2 import id_token
import requests

# Get Airflow variables. This is the recommended way to manage configuration.
gcp_project_id = Variable.get("gcp_project_id")
gcs_bucket = Variable.get("gcs_data_lake_bucket")
function_location = Variable.get("gcp_region")
mrt_station_ntmc_function_uri = Variable.get("mrt_station_ntmc_function_uri")
bq_dataset = "tpe_mrt_bronze"
bq_table = "mrt_station_ntmc"

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "start_date": datetime(2023, 1, 1),
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

@dag(
    dag_id="mrt_station_ntmc_source_to_bronze",
    default_args=default_args,
    schedule_interval="0 10 * * 6",  # Saturday at 10:00 AM
    catchup=False,
    tags=["mrt", "ntmc", "station", "bronze", "source", "incremental-load"],
)
def mrt_station_ntmc_ingestion_dag():
    """
    This DAG orchestrates the ingestion of NTMC MRT station data.
    """

    @task
    def get_id_token():
        auth_req = google.auth.transport.requests.Request()
        fetched_id_token = id_token.fetch_id_token(auth_req, mrt_station_ntmc_function_uri)
        return fetched_id_token

    @task
    def invoke_cloud_function(id_token: str):
        """
        Invokes the Cloud Function to fetch MRT station data.
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {id_token}",
        }
        response = requests.post(mrt_station_ntmc_function_uri, headers=headers, json={}, timeout=30)
        response.raise_for_status()
        return response.text

    id_token_task = get_id_token()
    invoke_cloud_function_task = invoke_cloud_function(id_token=id_token_task)

    load_gcs_to_bigquery = GCSToBigQueryOperator(
        task_id="load_station_data_to_bigquery",
        bucket=gcs_bucket,
        source_objects=[f"mrt_station_ntmc/mrt_station_ntmc_*.parquet"],
        destination_project_dataset_table=f"{gcp_project_id}.{bq_dataset}.{bq_table}",
        source_format="PARQUET",
        write_disposition="WRITE_TRUNCATE",  # Overwrite the table with new data
        autodetect=True,
        gcp_conn_id="google_cloud_default",
    )

    invoke_cloud_function_task >> load_gcs_to_bigquery

mrt_station_ntmc_ingestion_dag() 