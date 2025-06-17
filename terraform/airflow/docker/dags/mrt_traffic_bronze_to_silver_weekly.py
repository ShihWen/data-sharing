from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryExecuteQueryOperator, BigQueryInsertJobOperator
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.utils.dates import days_ago
from airflow.utils.trigger_rule import TriggerRule
import logging

# Import SQL queries from separate file
from sql.mrt_traffic_queries import (
    CHECK_NEW_DATA_QUERY,  # Legacy - kept for compatibility
    CHECK_PROCESSING_STRATEGY_QUERY,
    TRANSFORM_AND_LOAD_QUERY,  # Legacy - kept for compatibility
    TRANSFORM_AND_LOAD_INCREMENTAL_QUERY,
    GET_NEXT_BATCH_QUERY,
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

def determine_processing_strategy(**context):
    """
    Determine if this is a first run, incremental run, or no processing needed.
    Returns the appropriate task_id to branch to.
    """
    hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False
    )
    
    # Execute the strategy query
    job_config = {
        'query': {
            'query': CHECK_PROCESSING_STRATEGY_QUERY,
            'useLegacySql': False
        }
    }
    
    query_job = hook.insert_job(
        configuration=job_config,
        project_id=hook.project_id
    )
    
    results = query_job.result()
    strategy_info = list(results)[0]
    
    logging.info(f"Processing strategy determined: {dict(strategy_info)}")
    
    # Store strategy info in XCom for downstream tasks
    context['task_instance'].xcom_push(key='strategy_info', value=dict(strategy_info))
    
    run_type = strategy_info['run_type']
    
    if run_type == 'NO_NEW_DATA':
        logging.info("No new data to process")
        return 'no_processing_needed'
    elif run_type == 'FIRST_RUN':
        logging.info(f"First run detected - processing {strategy_info['records_diff']} records in batches")
        return 'process_first_run_batch'
    elif run_type == 'INCREMENTAL':
        logging.info(f"Incremental run - processing {strategy_info['records_diff']} new records")
        return 'process_incremental'
    else:
        logging.error(f"Unknown run type: {run_type}")
        raise ValueError(f"Unknown run type: {run_type}")

def process_batch(**context):
    """
    Process a batch of data for first run or incremental processing (month-based).
    """
    strategy_info = context['task_instance'].xcom_pull(key='strategy_info')
    
    if not strategy_info:
        raise ValueError("No strategy info found in XCom")
    
    run_type = strategy_info['run_type']
    start_month = strategy_info['batch_start_month']
    end_month = strategy_info['batch_end_month']
    months_to_process = strategy_info.get('months_to_process', 1)
    
    logging.info(f"Processing batch: {run_type} from {start_month} to {end_month} ({months_to_process} months)")
    
    # Prepare parameters for the SQL query (month-based)
    params = {
        'start_month': start_month,
        'end_month': end_month
    }
    
    # Store batch info for downstream tasks
    context['task_instance'].xcom_push(key='batch_info', value={
        'start_month': start_month,
        'end_month': end_month,
        'run_type': run_type,
        'months_to_process': months_to_process,
        'has_more_batches': strategy_info.get('has_more_batches', False)
    })
    
    return params

def check_batch_completion(**context):
    """
    Check if there are more batches to process for first run.
    """
    strategy_info = context['task_instance'].xcom_pull(key='strategy_info')
    
    if not strategy_info:
        return 'validate_processing'
    
    has_more_batches = strategy_info.get('has_more_batches', False)
    
    if has_more_batches:
        logging.info("More batches to process - triggering next batch")
        return 'get_next_batch'
    else:
        logging.info("All batches completed - proceeding to validation")
        return 'validate_processing'

def get_next_batch_params(**context):
    """
    Get parameters for the next batch processing (month-based).
    """
    hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False
    )
    
    job_config = {
        'query': {
            'query': GET_NEXT_BATCH_QUERY,
            'useLegacySql': False
        }
    }
    
    query_job = hook.insert_job(
        configuration=job_config,
        project_id=hook.project_id
    )
    
    results = query_job.result()
    next_batch_info = list(results)[0]
    
    logging.info(f"Next batch info: {dict(next_batch_info)}")
    
    # Prepare month-based parameters
    batch_params = {
        'start_month': str(next_batch_info['batch_start_month']),
        'end_month': str(next_batch_info['batch_end_month']),
        'months_in_batch': next_batch_info['months_in_batch'],
        'has_more_batches': next_batch_info['has_more_batches']
    }
    
    # Store next batch info in XCom
    context['task_instance'].xcom_push(key='next_batch_info', value=batch_params)
    
    return batch_params

def no_processing_needed(**context):
    """
    Log message when no processing is needed.
    """
    logging.info("No new data found - skipping processing")
    return "No processing needed"

dag = DAG(
    'mrt_traffic_bronze_to_silver_weekly',
    default_args=default_args,
    description='Enhanced MRT traffic data transfer from bronze to silver with smart batching',
    schedule_interval='0 10 * * 6',  # Run at 10 AM every Saturday
    start_date=days_ago(1),
    catchup=False,
    tags=['mrt', 'traffic', 'bronze', 'silver', 'enhanced'],
    on_success_callback=notify_success,
    on_failure_callback=notify_failure,
    max_active_runs=1  # Prevent parallel runs
)

# Determine processing strategy
determine_strategy = BranchPythonOperator(
    task_id='determine_processing_strategy',
    python_callable=determine_processing_strategy,
    dag=dag,
)

# No processing needed path
no_processing = PythonOperator(
    task_id='no_processing_needed',
    python_callable=no_processing_needed,
    dag=dag,
)

# Prepare batch parameters
prepare_batch = PythonOperator(
    task_id='prepare_batch_params',
    python_callable=process_batch,
    dag=dag,
)

# Process first run batch
process_first_run_batch = BigQueryExecuteQueryOperator(
    task_id='process_first_run_batch',
    sql=TRANSFORM_AND_LOAD_INCREMENTAL_QUERY,
    params={
        'start_month': '{{ ti.xcom_pull(task_ids="prepare_batch_params")["start_month"] }}',
        'end_month': '{{ ti.xcom_pull(task_ids="prepare_batch_params")["end_month"] }}'
    },
    use_legacy_sql=False,
    dag=dag,
)

# Process incremental data
process_incremental = BigQueryExecuteQueryOperator(
    task_id='process_incremental',
    sql=TRANSFORM_AND_LOAD_INCREMENTAL_QUERY, 
    params={
        'start_month': '{{ ti.xcom_pull(task_ids="prepare_batch_params")["start_month"] }}',
        'end_month': '{{ ti.xcom_pull(task_ids="prepare_batch_params")["end_month"] }}'
    },
    use_legacy_sql=False,
    dag=dag,
)

# Check if more batches are needed
check_completion = BranchPythonOperator(
    task_id='check_batch_completion',
    python_callable=check_batch_completion,
    dag=dag,
    trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS
)

# Get next batch parameters
get_next_batch = PythonOperator(
    task_id='get_next_batch',
    python_callable=get_next_batch_params,
    dag=dag,
)

# Process next batch (for first run continuation)
process_next_batch = BigQueryExecuteQueryOperator(
    task_id='process_next_batch',
    sql=TRANSFORM_AND_LOAD_INCREMENTAL_QUERY,
    params={
        'start_month': '{{ ti.xcom_pull(task_ids="get_next_batch")["start_month"] }}',
        'end_month': '{{ ti.xcom_pull(task_ids="get_next_batch")["end_month"] }}'
    },
    use_legacy_sql=False,
    dag=dag,
)

# Validate processing results
validate_processing = BigQueryExecuteQueryOperator(
    task_id='validate_processing',
    sql=VALIDATE_PROCESSING_QUERY,
    use_legacy_sql=False,
    dag=dag,
    trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS
)

# Set task dependencies
determine_strategy >> [no_processing, prepare_batch]

# First run and incremental paths
prepare_batch >> [process_first_run_batch, process_incremental]

# First run batch processing flow
process_first_run_batch >> check_completion
check_completion >> get_next_batch >> process_next_batch
process_next_batch >> check_completion

# Validation (triggered from multiple paths)
[process_incremental, check_completion] >> validate_processing 