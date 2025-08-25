from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryExecuteQueryOperator
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.utils.dates import days_ago
from airflow.utils.trigger_rule import TriggerRule
from airflow.models import Variable
import logging

from default_args import default_args
from dag_config import SCHEDULE_INTERVALS
from sql.c_store_seven_eleven_queries import (
    CHECK_DUPLICATE_STORE_QUERY
)


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
            'query': CHECK_NEW_DATA_QUERY,
            'useLegacySql': False
        }
    }
    
    query_job = hook.insert_job(
        configuration=job_config,
        project_id=hook.project_id
    )
    
    results = query_job.result()
    result = list(results)
    
    if result and result[0]['new_date']:
        new_date = result[0]['new_date'].strftime('%Y-%m-%d')
        logging.info(f"New date found: {new_date}")
        
        # Store the date to process for the next task
        context['task_instance'].xcom_push(key='target_date', value=new_date)
        return 'process_date'
    else:
        logging.info("No new date to process")
        return 'no_processing_needed'

def check_duplicate_store(**context):
    """
    Check for duplicate stores and decide which task to run next.
    Returns task_id for branching.
    """
    hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False
    )
    job_config = {
        'query': {
            'query': CHECK_DUPLICATE_STORE_QUERY,
            'useLegacySql': False
        }
    }
    query_job = hook.insert_job(
        configuration=job_config,
        project_id=hook.project_id
    )
    results = query_job.result()
    result = list(results)
    if result:
        logging.info(f"Duplicate stores found: {len(result)} stores")
        for row in result:
            logging.info(f"Duplicate store found: {row['name']}, {row['city']}")
        
        return 'process_duplicate_store'
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




# Task 2: Process the new month (only runs if new month found)
process_date = BigQueryExecuteQueryOperator(
    task_id='process_date',
    sql=TRANSFORM_AND_LOAD_DATE_QUERY,
    params={
        'target_date': '{{ ti.xcom_pull(task_ids="check_and_branch", key="target_date") }}'
    },
    use_legacy_sql=False,
    dag=dag,
)

check_and_branch >> check_duplicate_store