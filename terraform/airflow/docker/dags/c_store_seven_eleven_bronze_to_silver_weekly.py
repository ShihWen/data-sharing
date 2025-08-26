from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryExecuteQueryOperator, BigQueryInsertJobOperator
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.utils.dates import days_ago
from airflow.utils.trigger_rule import TriggerRule
from airflow.utils.task_group import TaskGroup
from airflow.models import Variable
import logging

from config.default_args import default_args
from config.dag_config import SCHEDULE_INTERVALS
from sql.c_store_seven_eleven_queries import (
    CHECK_NEW_DATA_QUERY,
    CHECK_DUPLICATE_STORE_QUERY,
    PROCESS_DUPLICATE_STORE_STEP1_LIST_DUPLICATE_STORES,
    PROCESS_DUPLICATE_STORE_STEP2_REMOVE_EXACT_DUPLICATE_STORES
)


# Get Airflow variables. This is the recommended way to manage configuration.
gcp_project_id = Variable.get("gcp_project_id")
BRONZE_DATASET = "c_store_bronze"
SILVER_DATASET = "c_store_silver"

def notify_success(context):
    """Send email notification on success"""
    send_notification(
        context=context,
        status='success',
        email_list=default_args['email']
    )

def notify_failure(context):
    """Send email notification on failure"""
    send_notification(
        context=context,
        status='failure',
        email_list=default_args['email'],
        include_exception=True
    )

def check_and_decide(**context):
    """
    Check if there's a new date and decide which task to run next.
    Returns task_id for branching.
    """
    hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False
    )
    
    # Execute the check query
    job_config = {
        'query': {
            'query': CHECK_NEW_DATA_QUERY.format(
                project_id=gcp_project_id,
                bronze_dataset_id=BRONZE_DATASET,
                silver_dataset_id=SILVER_DATASET
            ),
            'useLegacySql': False
        }
    }
    
    query_job = hook.insert_job(
        configuration=job_config,
        project_id=gcp_project_id
    )
    
    results = query_job.result()
    result = list(results)
    
    if result and result[0]['new_date']:
        new_date = result[0]['new_date']#.strftime('%Y-%m-%d')
        logging.info(f"New date found: {new_date}")
        
        # Store the date to process for the next task
        context['task_instance'].xcom_push(key='target_date', value=new_date)
        return 'check_duplicate_store'
    else:
        logging.info("No new date to process")
        return 'log_no_processing'

def check_duplicate_store(**context):
    """
    Check for duplicate stores and decide which task to run next.
    Returns task_id for branching.
    """
    hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False
    )
    
    # Get the target date from the previous task
    target_date = context['task_instance'].xcom_pull(task_ids='check_and_branch', key='target_date')
    
    if not target_date:
        logging.info("No target date found, skipping duplicate store check")
        return 'no_processing_needed'
    
    job_config = {
        'query': {
            'query': CHECK_DUPLICATE_STORE_QUERY.format(
                project_id=gcp_project_id,
                bronze_dataset_id=BRONZE_DATASET,
                target_date=target_date
            ),
            'useLegacySql': False
        }
    }
    query_job = hook.insert_job(
        configuration=job_config,
        project_id=gcp_project_id
    )
    results = query_job.result()
    result = list(results)
    if result:
        logging.info(f"Duplicate stores found: {len(result)} stores")
        for row in result:
            logging.info(f"Duplicate store found: {row['name']}, {row['city']}")
        
        return 'process_duplicate_store_step1_list_duplicate_stores'
    else:
        logging.info("No duplicate stores found")
        return 'no_processing_needed'



def log_no_processing(**context):
    """Log when no processing is needed"""
    logging.info("No new data found - skipping processing")
    return "No processing needed"


# Create the DAG
dag = DAG(
    'c_store_seven_eleven_bronze_to_silver_weekly',
    default_args=default_args,
    description='C store seven eleven data transfer from bronze to silver (one date at a time)',
    schedule_interval= SCHEDULE_INTERVALS['weekly'],  # Run at 10 AM every Saturday on Taiwan time
    start_date=days_ago(1),
    catchup=False,
    tags=['c_store', 'seven_eleven', 'bronze', 'silver', 'incremental-load'],
    on_success_callback=notify_success,
    on_failure_callback=notify_failure,
    max_active_runs=1
)

# Task 1: Check for new month and decide next step
check_and_branch = BranchPythonOperator(
    task_id='check_and_branch',
    python_callable=check_and_decide,
    dag=dag,
)

# Task 2: Check for duplicate stores
check_duplicate_store = BranchPythonOperator(
    task_id='check_duplicate_store',
    python_callable=check_duplicate_store,
    dag=dag,
)

# Task 3: Log when no processing is needed
no_processing_needed = PythonOperator(
    task_id='no_processing_needed',
    python_callable=log_no_processing,
    dag=dag,
)

    with TaskGroup(group_id='process_duplicate_store') as process_duplicate_store:
        # Task 4: Process duplicate stores (placeholder for now)
        step1_list_duplicate_stores = BigQueryInsertJobOperator(
            dag=dag,
            task_id='process_duplicate_store_step1_list_duplicate_stores',
            configuration={
                "query": {
                    "query": PROCESS_DUPLICATE_STORE_STEP1_LIST_DUPLICATE_STORES.format(
                        project_id=gcp_project_id,
                        bronze_dataset_id=BRONZE_DATASET,
                        target_date=target_date
                    ),
                    "useLegacySql": False,
                }
            },
        )

        step2_remove_exact_duplicate_stores = BigQueryInsertJobOperator(
            dag=dag,
            task_id='process_duplicate_store_step2_remove_exact_duplicate_stores',
            configuration={
                "query": {
                    "query": PROCESS_DUPLICATE_STORE_STEP2_REMOVE_EXACT_DUPLICATE_STORES.format(
                        project_id=gcp_project_id,
                        bronze_dataset_id=BRONZE_DATASET,
                        target_date=target_date
                    ),
                    "useLegacySql": False,
                }
            },
        )

        step1_list_duplicate_stores >> step2_remove_exact_duplicate_stores



# DAG flow with proper branching
check_and_branch >> [ check_duplicate_store, no_processing_needed]
check_duplicate_store >> [process_duplicate_store, no_processing_needed]