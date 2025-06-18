from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryExecuteQueryOperator
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.utils.dates import days_ago
from airflow.utils.trigger_rule import TriggerRule
import logging

# Import SQL queries from separate file
from sql.mrt_traffic_queries import (
    CHECK_NEW_MONTH_QUERY,
    TRANSFORM_AND_LOAD_MONTH_QUERY,
    VALIDATE_PROCESSING_QUERY
)

# Import common functions
from utils.common_functions import (
    get_airflow_variable,
    send_notification
)

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'email': get_airflow_variable('notification_email', ['your-email@example.com'])
}

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
    Check if there's a new month and decide which task to run next.
    Returns task_id for branching.
    """
    hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False
    )
    
    # Execute the check query
    job_config = {
        'query': {
            'query': CHECK_NEW_MONTH_QUERY,
            'useLegacySql': False
        }
    }
    
    query_job = hook.insert_job(
        configuration=job_config,
        project_id=hook.project_id
    )
    
    results = query_job.result()
    result = list(results)
    
    if result and result[0]['new_month']:
        new_month = result[0]['new_month'].strftime('%Y-%m-%d')
        logging.info(f"New month found: {new_month}")
        
        # Store the month to process for the next task
        context['task_instance'].xcom_push(key='target_month', value=new_month)
        return 'process_month'
    else:
        logging.info("No new month to process")
        return 'no_processing_needed'

def log_no_processing(**context):
    """Log when no processing is needed"""
    logging.info("No new data found - skipping processing")
    return "No processing needed"

# Create the DAG
dag = DAG(
    'mrt_traffic_bronze_to_silver_weekly',
    default_args=default_args,
    description='SIMPLIFIED: MRT traffic data transfer from bronze to silver (one month at a time)',
    schedule_interval='0 10 * * 6',  # Run at 10 AM every Saturday
    start_date=days_ago(1),
    catchup=False,
    tags=['mrt', 'traffic', 'bronze', 'silver', 'simplified'],
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

# Task 2: Process the new month (only runs if new month found)
process_month = BigQueryExecuteQueryOperator(
    task_id='process_month',
    sql=TRANSFORM_AND_LOAD_MONTH_QUERY,
    params={
        'target_month': '{{ ti.xcom_pull(task_ids="check_and_branch", key="target_month") }}'
    },
    use_legacy_sql=False,
    dag=dag,
)

# Task 3: Validate processing results
validate_processing = BigQueryExecuteQueryOperator(
    task_id='validate_processing',
    sql=VALIDATE_PROCESSING_QUERY,
    use_legacy_sql=False,
    dag=dag,
)

# Task 4: Log when no processing needed
no_processing_needed = PythonOperator(
    task_id='no_processing_needed',
    python_callable=log_no_processing,
    dag=dag,
)

# Simple task dependencies
check_and_branch >> [process_month, no_processing_needed]
process_month >> validate_processing 