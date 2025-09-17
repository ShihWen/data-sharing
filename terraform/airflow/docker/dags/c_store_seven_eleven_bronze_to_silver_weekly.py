from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from airflow.utils.dates import days_ago
from airflow.utils.task_group import TaskGroup
from airflow.utils.trigger_rule import TriggerRule
from airflow.models import Variable
import logging

from config.default_args import default_args
from config.dag_config import SCHEDULE_INTERVALS
from sql.c_store_seven_eleven_queries import (
    CHECK_NEW_DATA_QUERY,
    CHECK_DUPLICATE_STORE_QUERY,
    PROCESS_DUPLICATE_STORE_STEP1_LIST_DUPLICATE_STORES,
    PROCESS_DUPLICATE_STORE_STEP2_REMOVE_EXACT_DUPLICATE_STORES,
    PROCESS_DUPLICATE_STORE_STEP3_REMOVE_STORE_IN_SOUTH_DISTRICT_TAINAN,
    PROCESS_DUPLICATE_STORE_STEP4_REMOVE_SHORTER_SERVICE_STORE,
    INSERT_DATA_TO_SILVER_QUERY,
    INSERT_NO_DUPLICATE_DATA_TO_SILVER_QUERY
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
        return 'decide_duplicate_store_branch'
    else:
        logging.info("No new date to process")
        return 'no_processing_needed'

def decide_duplicate_store_branch(**context):
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
        
        return 'process_duplicate_store.step1_list_duplicate_stores'
    else:
        logging.info("No duplicate stores found")
        return 'insert_no_duplicate_data_to_silver'

def insert_data_without_duplicates(**context):
    """
    List duplicate stores.
    """
    target_date = context['task_instance'].xcom_pull(task_ids='check_and_branch', key='target_date')

    bq_hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False
    )

    sql = INSERT_NO_DUPLICATE_DATA_TO_SILVER_QUERY.format(
        project_id=gcp_project_id,
        bronze_dataset_id=BRONZE_DATASET,
        silver_dataset_id=SILVER_DATASET,
        target_date=target_date
    )
    bq_hook.run_query(sql)



def step1_list_duplicate_stores(**context):
    """
    List duplicate stores.
    """
    target_date = context['task_instance'].xcom_pull(task_ids='check_and_branch', key='target_date')

    bq_hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False
    )

    sql = PROCESS_DUPLICATE_STORE_STEP1_LIST_DUPLICATE_STORES.format(
        project_id=gcp_project_id,
        bronze_dataset_id=BRONZE_DATASET,
        silver_dataset_id=SILVER_DATASET,
        target_date=target_date
    )
    bq_hook.run_query(sql)


def step2_remove_exact_duplicate_stores(**context):
    """
    Remove exact duplicate stores.
    """
    target_date = context['task_instance'].xcom_pull(task_ids='check_and_branch', key='target_date')
    
    bq_hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False
    )
    
    sql = PROCESS_DUPLICATE_STORE_STEP2_REMOVE_EXACT_DUPLICATE_STORES.format(
        project_id=gcp_project_id,
        silver_dataset_id=SILVER_DATASET,
        target_date=target_date
    )
    bq_hook.run_query(sql)
    
def step3_remove_store_in_south_district_tainan(**context):
    """
    Remove store in south district of Tainan.
    """
    target_date = context['task_instance'].xcom_pull(task_ids='check_and_branch', key='target_date')

    bq_hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False
    )

    sql = PROCESS_DUPLICATE_STORE_STEP3_REMOVE_STORE_IN_SOUTH_DISTRICT_TAINAN.format(
        project_id=gcp_project_id,
        silver_dataset_id=SILVER_DATASET,
        target_date=target_date
    )
    bq_hook.run_query(sql)


def step4_remove_shorter_service_store(**context):
    """
    Remove shorter service store.
    """

    bq_hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False
    )

    sql = PROCESS_DUPLICATE_STORE_STEP4_REMOVE_SHORTER_SERVICE_STORE.format(
        project_id=gcp_project_id,
        silver_dataset_id=SILVER_DATASET
    )
    bq_hook.run_query(sql)


def log_no_processing(**context):
    """Log when no processing is needed"""
    logging.info("No new data found - skipping processing")
    return "No processing needed"


# Create the DAG
with DAG(
    'c_store_seven_eleven_bronze_to_silver_weekly',
    default_args=default_args,
    description='C store seven eleven data transfer from bronze to silver (one date at a time)',
    schedule_interval= SCHEDULE_INTERVALS['weekly'],  # Run at 10 AM every Saturday on Taiwan time
    start_date=pendulum.datetime(2023, 1, 1, tz="UTC"),
    catchup=False,
    tags=['c_store', 'seven_eleven', 'bronze', 'silver', 'incremental-load'],
    on_success_callback=notify_success,
    on_failure_callback=notify_failure,
    max_active_runs=1
) as dag:

    # Task 1: Check for new month and decide next step
    check_and_branch = BranchPythonOperator(
        task_id='check_and_branch',
        python_callable=check_and_decide,
        dag=dag,
    )

    # Task 2: Check for duplicate stores
    decide_duplicate_store_branch = BranchPythonOperator(
        task_id='decide_duplicate_store_branch',
        python_callable=decide_duplicate_store_branch,
        dag=dag,
    )

    insert_no_duplicate_data_to_silver = PythonOperator(
        task_id='insert_no_duplicate_data_to_silver',
        python_callable=insert_data_without_duplicates,
        dag=dag,
    )

    # Task 3: Log when no processing is needed
    no_processing_needed = PythonOperator(
        task_id='no_processing_needed',
        python_callable=log_no_processing,
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS,
        dag=dag,
    )

    # Task 4: Process duplicate stores
    with TaskGroup(group_id='process_duplicate_store') as process_duplicate_store:
        
        step1_task = PythonOperator(
            task_id='step1_list_duplicate_stores',
            python_callable=step1_list_duplicate_stores,
            dag=dag,
        )

        step2_task = PythonOperator(
            task_id='step2_remove_exact_duplicate_stores',
            python_callable=step2_remove_exact_duplicate_stores,
            dag=dag,
        )

        step3_task = PythonOperator(
            task_id='step3_remove_store_in_south_district_tainan',
            python_callable=step3_remove_store_in_south_district_tainan,
            dag=dag,
        )

        step4_task = PythonOperator(
            task_id='step4_remove_shorter_service_store',
            python_callable=step4_remove_shorter_service_store,
            dag=dag,
        )

        step1_task >> step2_task >> step3_task >> step4_task

    # Task 5: insert data to silver dataset
    insert_data_to_silver = BigQueryInsertJobOperator(
        task_id='insert_data_to_silver',
        configuration={
            "query": {
                "query": INSERT_DATA_TO_SILVER_QUERY.format(
                    project_id=gcp_project_id,
                    silver_dataset_id=SILVER_DATASET,
                ),
                "useLegacySql": False
            }
        },
    )



    # DAG flow with proper branching
    check_and_branch >> [ decide_duplicate_store_branch, no_processing_needed]
    decide_duplicate_store_branch >> [process_duplicate_store, insert_no_duplicate_data_to_silver]
    process_duplicate_store >> insert_data_to_silver