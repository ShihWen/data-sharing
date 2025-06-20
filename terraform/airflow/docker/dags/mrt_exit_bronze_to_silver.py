from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryExecuteQueryOperator
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.utils.dates import days_ago
from airflow.models import Variable
from airflow.utils.trigger_rule import TriggerRule
import logging

# Import SQL queries from separate file
from sql.mrt_exit_queries import (
    CHECK_NEW_VERSIONS_QUERY,
    TRANSFORM_AND_LOAD_NEW_VERSIONS_QUERY,
    VALIDATE_PROCESSING_QUERY,
    DATA_QUALITY_SUMMARY_QUERY
)

# Import common functions
from utils.common_functions import (
    get_airflow_variable,
    send_notification
)

# Get the location at module level to use in operators
BIGQUERY_LOCATION = Variable.get('bigquery_location', 'asia-east1')

default_args = {
    'owner': 'data_engineering',
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

def check_new_versions_and_decide(**context):
    """
    Check if there are new versions in bronze and decide which task to run next.
    Returns task_id for branching.
    """
    hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False,
        location=BIGQUERY_LOCATION
    )
    
    # Render the SQL to handle Jinja templating within the PythonOperator
    rendered_query = context['task_instance'].render_template(CHECK_NEW_VERSIONS_QUERY)
    
    # Execute the check query
    job_config = {
        'query': {
            'query': rendered_query,
            'useLegacySql': False
        }
    }
    
    query_job = hook.insert_job(
        configuration=job_config,
        project_id=hook.project_id,
        location=BIGQUERY_LOCATION
    )
    
    results = query_job.result()
    result = list(results)
    
    if result and result[0]['has_new_versions']:
        new_version_count = result[0]['new_version_count']
        min_version = result[0]['min_new_version']
        max_version = result[0]['max_new_version']
        
        logging.info(f"Found {new_version_count} new versions to process (versions {min_version} to {max_version})")
        
        # Store processing stats for the next task
        context['task_instance'].xcom_push(key='new_version_count', value=new_version_count)
        context['task_instance'].xcom_push(key='min_version', value=min_version)
        context['task_instance'].xcom_push(key='max_version', value=max_version)
        
        return 'process_new_versions'
    else:
        logging.info("No new versions found - skipping processing")
        return 'no_processing_needed'

def log_no_processing(**context):
    """Log when no processing is needed"""
    logging.info("No new exit data versions found - skipping processing")
    return "No processing needed"

def log_processing_summary(**context):
    """Log summary of what was processed"""
    new_version_count = context['task_instance'].xcom_pull(task_ids='check_and_branch', key='new_version_count')
    min_version = context['task_instance'].xcom_pull(task_ids='check_and_branch', key='min_version')
    max_version = context['task_instance'].xcom_pull(task_ids='check_and_branch', key='max_version')
    
    logging.info(f"""
    MRT Exit Processing Summary:
    - Processed {new_version_count} new versions
    - Version range: {min_version} to {max_version}
    - Processing completed successfully
    """)
    return "Processing summary logged"

# Create the DAG
dag = DAG(
    'mrt_exit_bronze_to_silver',
    default_args=default_args,
    description='Transform MRT exit data from bronze to silver layer with version-based incremental processing',
    schedule_interval='0 10 * * 6',  # Run at 10 AM every Saturday
    start_date=days_ago(1),
    catchup=False,
    tags=['mrt', 'exit', 'bronze', 'silver', 'incremental-load', 'version-based'],
    on_success_callback=notify_success,
    on_failure_callback=notify_failure,
    max_active_runs=1
)

# Task 1: Check for new versions and decide next step
check_and_branch = BranchPythonOperator(
    task_id='check_and_branch',
    python_callable=check_new_versions_and_decide,
    dag=dag,
)

# Task 2: Process new versions (only runs if new versions found)
process_new_versions = BigQueryExecuteQueryOperator(
    task_id='process_new_versions',
    sql=TRANSFORM_AND_LOAD_NEW_VERSIONS_QUERY,
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

# Task 4: Generate data quality summary report
data_quality_summary = BigQueryExecuteQueryOperator(
    task_id='data_quality_summary',
    sql=DATA_QUALITY_SUMMARY_QUERY,
    use_legacy_sql=False,
    dag=dag,
)

# Task 5: Log processing summary
log_summary = PythonOperator(
    task_id='log_processing_summary',
    python_callable=log_processing_summary,
    dag=dag,
)

# Task 6: Log when no processing needed
no_processing_needed = PythonOperator(
    task_id='no_processing_needed',
    python_callable=log_no_processing,
    dag=dag,
)

# Task dependencies
check_and_branch >> [process_new_versions, no_processing_needed]
process_new_versions >> validate_processing >> data_quality_summary >> log_summary 