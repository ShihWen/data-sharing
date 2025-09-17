# -*- coding: utf-8 -*-
"""
### MRT Station Bronze to Silver DAG

This DAG is responsible for transforming MRT station data from the bronze layer to the silver layer.

**Key Features:**
- **SCD2 Implementation:** Uses Slowly Changing Dimension Type 2 to track historical changes.
- **Idempotent & Incremental:** Uses a version-based check to only process new data.
- **Scheduled Execution:** Runs every Saturday at 10:00 AM.
- **Data Cleansing:** Standardizes data types and structures.
- **Data Enrichment:** Parses station addresses and adds data quality metrics.
- **Templated SQL:** Uses Jinja templating for environment-specific details.
"""

from __future__ import annotations

import pendulum

from airflow.models.dag import DAG
from airflow.operators.python import ShortCircuitOperator
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.providers.google.cloud.operators.bigquery import BigQueryExecuteQueryOperator
from airflow.utils.dates import days_ago
import logging

# --- Import Queries ---
from sql.mrt_station_queries import CHECK_NEW_VERSIONS_QUERY, MERGE_SCD2_MRT_STATION, INSERT_UPDATED_MRT_STATION

# --- DAG Configuration ---
DAG_ID = "mrt_station_bronze_to_silver"
DESCRIPTION = "Loads new MRT station data from bronze to silver using SCD2 pattern, parsing and enriching it."
SCHEDULE_INTERVAL = '0 2 * * 6'  # Run at 10 AM every Saturday on Taiwan time
START_DATE = pendulum.datetime(2023, 1, 1, tz="UTC")
CATCHUP = False
TAGS = ["mrt", "station", "bronze", "silver", "incremental-load", "trtc", "scd2"]

# --- BigQuery Configuration ---
GCP_CONN_ID = "google_cloud_default"
# The project ID will be fetched from Airflow variables directly in the SQL templates.
BRONZE_DATASET = "tpe_mrt_bronze"
SILVER_DATASET = "tpe_mrt_silver"
BIGQUERY_LOCATION = "asia-east1"

def _check_for_new_data_func(**context):
    """
    Executes a query to check for new versions and returns True if new data exists.
    """
    rendered_sql = context["task_instance"].task.render_template(CHECK_NEW_VERSIONS_QUERY, context)
    
    logging.info("Checking for new station versions...")
    logging.info(f"Executing query: {rendered_sql}")
    
    hook = BigQueryHook(gcp_conn_id=GCP_CONN_ID
                        , use_legacy_sql=False
                        ,location=BIGQUERY_LOCATION)
    
    # get_first returns a tuple, e.g., (2,)
    result = hook.get_first(rendered_sql)
    
    new_version_count = result[0] if result and result[0] is not None else 0
    
    logging.info(f"Found {new_version_count} new versions to process.")
    
    if new_version_count > 0:
        return True
    
    logging.info("No new versions found. Skipping downstream tasks.")
    return False

with DAG(
    dag_id=DAG_ID,
    description=DESCRIPTION,
    schedule=SCHEDULE_INTERVAL,
    start_date=START_DATE,
    catchup=CATCHUP,
    tags=TAGS,
    template_searchpath="/usr/local/airflow/dags/",
    doc_md=__doc__,
) as dag:
    # Task 1: Check if there is new data to process
    check_for_new_data = ShortCircuitOperator(
        task_id="check_for_new_data",
        python_callable=_check_for_new_data_func,
        doc_md="Checks if there are new `VersionID`s in the bronze table. Continues if count > 0, otherwise skips.",
    )

    # Task 2: Execute the SCD2 MERGE (Step 1) - Mark changed records as inactive
    merge_scd2_mrt_station = BigQueryExecuteQueryOperator(
        task_id="merge_scd2_mrt_station",
        sql=MERGE_SCD2_MRT_STATION,
        use_legacy_sql=False,
        gcp_conn_id=GCP_CONN_ID,
        location=BIGQUERY_LOCATION,
        params={
            "bronze_dataset": BRONZE_DATASET,
            "silver_dataset": SILVER_DATASET,
        },
        doc_md="Executes the SCD2 MERGE statement to mark changed records as inactive and insert new records.",
    )

    # Task 3: Execute the SCD2 INSERT (Step 2) - Insert updated versions of changed records
    insert_updated_mrt_station = BigQueryExecuteQueryOperator(
        task_id="insert_updated_mrt_station",
        sql=INSERT_UPDATED_MRT_STATION,
        use_legacy_sql=False,
        gcp_conn_id=GCP_CONN_ID,
        location=BIGQUERY_LOCATION,
        params={
            "bronze_dataset": BRONZE_DATASET,
            "silver_dataset": SILVER_DATASET,
        },
        doc_md="Executes the SCD2 INSERT statement to create new versions of changed records.",
    )

    # --- Task Dependencies ---
    check_for_new_data >> merge_scd2_mrt_station >> insert_updated_mrt_station 