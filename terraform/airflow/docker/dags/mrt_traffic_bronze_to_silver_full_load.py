from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryExecuteQueryOperator
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.utils.dates import days_ago
import logging

# Import SQL queries from separate file
from sql.mrt_traffic_full_load_queries import (
    CHECK_PREREQUISITES_QUERY,
    FULL_LOAD_YEAR_BATCH_QUERY,
    FULL_LOAD_VALIDATION_QUERY,
    COST_ESTIMATION_QUERY
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
    'retries': 3,
    'retry_delay': timedelta(minutes=10),
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

def process_prerequisites_result(**context):
    """
    Process the results from check_prerequisites task.
    This function receives the query results and processes them.
    """
    # Get the results from the previous task
    task_instance = context['task_instance']
    dag_run = context['dag_run']
    
    # The check_prerequisites_query task stores results in XCom
    # We need to retrieve them from the BigQuery operator
    logging.info("Processing prerequisites check results...")
    
    # Note: The actual prerequisite logic will be handled by the BigQuery operator
    # This function mainly serves as a checkpoint and logging
    
    return "Prerequisites processed successfully"

def process_cost_estimation_result(**context):
    """
    Process the results from cost estimation query.
    """
    logging.info("💰 Cost estimation completed. Check the previous task logs for detailed breakdown.")
    return "Cost estimation processed successfully"

def process_full_load_years(**context):
    """
    Coordinate the year-by-year processing.
    Since we need to process multiple years, we'll do this in a loop.
    """
    # Get variables using Airflow's Variable model for proper resolution
    from airflow.models import Variable
    
    hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False,
        location=Variable.get('bigquery_location', 'asia-east1')  # Use Variable.get for proper resolution
    )
    
    # Process years from 2017 to 2025
    years_to_process = list(range(2017, 2026))
    total_processed = 0
    
    for year in years_to_process:
        logging.info(f"🔄 Processing year {year}...")
        
        # Get the Airflow variables using proper Variable model
        project_id = Variable.get('project_id')
        bronze_dataset = Variable.get('tpe_mrt_bronze_dataset_id')
        silver_dataset = Variable.get('tpe_mrt_silver_dataset_id')
        location = Variable.get('bigquery_location', 'asia-east1')
        
        # Manually render the SQL template
        rendered_sql = FULL_LOAD_YEAR_BATCH_QUERY.replace(
            '{{ var.value.project_id }}', project_id
        ).replace(
            '{{ var.value.tpe_mrt_bronze_dataset_id }}', bronze_dataset
        ).replace(
            '{{ var.value.tpe_mrt_silver_dataset_id }}', silver_dataset
        ).replace(
            '{{ params.target_year }}', str(year)
        )
        
        logging.info(f"🌏 Using BigQuery location: {location}")
        
        job_config = {
            'query': {
                'query': rendered_sql,
                'useLegacySql': False
            }
        }
        
        query_job = hook.insert_job(
            configuration=job_config,
            project_id=project_id,
            location=location  # Explicitly set location
        )
        
        result = query_job.result()
        rows_processed = result.num_dml_affected_rows or 0
        total_processed += rows_processed
        
        logging.info(f"✅ Year {year} completed: {rows_processed:,} records processed in {location}")
    
    logging.info(f"🎉 Full load completed: {total_processed:,} total records processed")
    
    # Store processing info
    context['task_instance'].xcom_push(key='processing_results', value={
        'total_processed': total_processed,
        'years_processed': len(years_to_process)
    })
    
    return f"Processed {total_processed:,} records across {len(years_to_process)} years"

# Create the DAG
dag = DAG(
    'mrt_traffic_bronze_to_silver_full_load',
    default_args=default_args,
    description='FULL LOAD: MRT traffic data from bronze to silver (pairs with weekly incremental DAG)',
    schedule_interval=None,  # Manual trigger only
    start_date=days_ago(1),
    catchup=False,
    tags=['mrt', 'traffic', 'full-load', 'bronze', 'silver', 'paired-with-weekly'],
    on_success_callback=notify_success,
    on_failure_callback=notify_failure,
    max_active_runs=1
)

# Task 1: Check prerequisites using BigQueryExecuteQueryOperator
check_prerequisites_query = BigQueryExecuteQueryOperator(
    task_id='check_prerequisites',
    sql=CHECK_PREREQUISITES_QUERY,
    use_legacy_sql=False,
    location='{{ var.value.bigquery_location }}',  # Use Airflow templating
    dag=dag,
)

# Task 2: Process prerequisites results
process_prerequisites_task = PythonOperator(
    task_id='process_prerequisites',
    python_callable=process_prerequisites_result,
    dag=dag,
)

# Task 3: Estimate costs using BigQueryExecuteQueryOperator
estimate_costs_query = BigQueryExecuteQueryOperator(
    task_id='estimate_costs',
    sql=COST_ESTIMATION_QUERY,
    use_legacy_sql=False,
    location='{{ var.value.bigquery_location }}',  # Use Airflow templating
    dag=dag,
)

# Task 4: Process cost estimation results
process_costs_task = PythonOperator(
    task_id='process_costs',
    python_callable=process_cost_estimation_result,
    dag=dag,
)

# Task 5: Process full load in optimized batches
process_full_load_task = PythonOperator(
    task_id='process_full_load',
    python_callable=process_full_load_years,
    dag=dag,
)

# Task 6: Final validation using BigQueryExecuteQueryOperator
final_validation_query = BigQueryExecuteQueryOperator(
    task_id='final_validation',
    sql=FULL_LOAD_VALIDATION_QUERY,
    use_legacy_sql=False,
    location='{{ var.value.bigquery_location }}',  # Use Airflow templating
    dag=dag,
)

# Set up dependencies
check_prerequisites_query >> process_prerequisites_task >> estimate_costs_query >> process_costs_task >> process_full_load_task >> final_validation_query 