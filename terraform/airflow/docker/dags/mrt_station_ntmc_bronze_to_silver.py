import os
from datetime import datetime, timedelta
from airflow.decorators import dag, task
from airflow.models import Variable
from airflow.providers.google.cloud.operators.functions import CloudFunctionInvokeFunctionOperator
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator

# Get Airflow variables. This is the recommended way to manage configuration.
gcp_project_id = Variable.get("gcp_project_id")
gcs_bucket = Variable.get("gcs_data_lake_bucket")
function_location = Variable.get("gcp_region")
function_name = "mrt-station-ntmc-fetcher"
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
    dag_id="mrt_station_ntmc_bronze_to_silver",
    default_args=default_args,
    schedule_interval="0 10 * * 6",  # Saturday at 10:00 AM
    catchup=False,
    tags=["mrt", "ntmc", "station", "bronze", "silver", "incremental-load"],
)
def mrt_station_ntmc_ingestion_dag():
    """
    This DAG orchestrates the ingestion of NTMC MRT station data.
    """

    invoke_cloud_function = CloudFunctionInvokeFunctionOperator(
        task_id="invoke_mrt_station_ntmc_fetcher",
        project_id=gcp_project_id,
        location=function_location,
        function_id=function_name,
        input_data={},
        gcp_conn_id="google_cloud_default",
    )

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

    invoke_cloud_function >> load_gcs_to_bigquery

mrt_station_ntmc_ingestion_dag() 