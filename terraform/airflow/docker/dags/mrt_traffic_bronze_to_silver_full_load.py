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

def check_prerequisites(**context):
    """
    Check if full load is needed and validate prerequisites.
    """
    hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False
    )
    
    job_config = {
        'query': {
            'query': CHECK_PREREQUISITES_QUERY,
            'useLegacySql': False
        }
    }
    
    query_job = hook.insert_job(
        configuration=job_config,
        project_id=hook.project_id
    )
    
    results = query_job.result()
    result = list(results)[0]
    
    logging.info(f"Prerequisites check:")
    logging.info(f"Bronze: {result['bronze_records']} records, {result['bronze_months']} months")
    logging.info(f"Silver: {result['silver_records']} records, {result['silver_months']} months")
    logging.info(f"Status: {result['load_status']}")
    
    if result['load_status'] == 'ALREADY_COMPLETE':
        raise Exception("Full load already complete! Silver table has same record count as bronze.")
    
    # Store info for downstream tasks
    context['task_instance'].xcom_push(key='load_info', value=dict(result))
    
    return f"Ready for full load: {result['load_status']}"

def estimate_costs(**context):
    """
    Estimate processing costs before running the full load.
    This helps users understand the expected BigQuery costs.
    """
    hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False
    )
    
    job_config = {
        'query': {
            'query': COST_ESTIMATION_QUERY,
            'useLegacySql': False
        }
    }
    
    query_job = hook.insert_job(
        configuration=job_config,
        project_id=hook.project_id
    )
    
    results = query_job.result()
    
    total_processing_cost = 0
    total_storage_cost = 0
    total_records = 0
    total_gb = 0
    
    logging.info("💰 COST ESTIMATION BREAKDOWN:")
    logging.info("=" * 60)
    
    for row in results:
        year = row['year']
        records = row['records_per_year']
        gb_size = row['estimated_gb_per_year']
        processing_cost = row['estimated_processing_cost_usd']
        storage_cost = row['estimated_storage_cost_monthly_usd']
        
        total_records += records
        total_gb += gb_size
        total_processing_cost += processing_cost
        total_storage_cost += storage_cost
        
        logging.info(f"Year {year}: {records:,} records, {gb_size} GB")
        logging.info(f"  → Processing cost: ${processing_cost}")
        logging.info(f"  → Monthly storage: ${storage_cost}")
        logging.info("-" * 40)
    
    logging.info("📊 TOTAL ESTIMATED COSTS:")
    logging.info(f"Total records to process: {total_records:,}")
    logging.info(f"Total data size: {total_gb:.2f} GB")
    logging.info(f"💵 One-time processing cost: ${total_processing_cost:.2f}")
    logging.info(f"💾 Monthly storage cost: ${total_storage_cost:.3f}")
    logging.info("=" * 60)
    
    # Store cost info for monitoring
    cost_info = {
        'total_records': total_records,
        'total_gb': total_gb,
        'processing_cost_usd': total_processing_cost,
        'storage_cost_monthly_usd': total_storage_cost
    }
    
    context['task_instance'].xcom_push(key='cost_estimation', value=cost_info)
    
    return f"Estimated cost: ${total_processing_cost:.2f} processing + ${total_storage_cost:.3f}/month storage"

def process_full_load_optimized(**context):
    """
    Process the full load in optimized batches.
    Uses year-based batches for better performance.
    """
    hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False
    )
    
    # Process years from 2017 to 2025
    years_to_process = list(range(2017, 2026))
    total_processed = 0
    
    for year in years_to_process:
        logging.info(f"🔄 Processing year {year}...")
        
        job_config = {
            'query': {
                'query': FULL_LOAD_YEAR_BATCH_QUERY,
                'useLegacySql': False,
                'parameterMode': 'NAMED',
                'queryParameters': [
                    {
                        'name': 'target_year',
                        'parameterType': {'type': 'INT64'},
                        'parameterValue': {'value': str(year)}
                    }
                ]
            }
        }
        
        query_job = hook.insert_job(
            configuration=job_config,
            project_id=hook.project_id
        )
        
        result = query_job.result()
        rows_processed = result.num_dml_affected_rows or 0
        total_processed += rows_processed
        
        logging.info(f"✅ Year {year} completed: {rows_processed:,} records processed")
    
    logging.info(f"🎉 Full load completed: {total_processed:,} total records processed")
    
    # Store processing info
    context['task_instance'].xcom_push(key='processing_results', value={
        'total_processed': total_processed,
        'years_processed': len(years_to_process)
    })
    
    return f"Processed {total_processed:,} records across {len(years_to_process)} years"

def validate_full_load(**context):
    """Validate the full load results"""
    hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False
    )
    
    job_config = {
        'query': {
            'query': FULL_LOAD_VALIDATION_QUERY,
            'useLegacySql': False
        }
    }
    
    query_job = hook.insert_job(
        configuration=job_config,
        project_id=hook.project_id
    )
    
    results = query_job.result()
    
    validation_results = []
    for row in results:
        row_dict = dict(row)
        validation_results.append(row_dict)
        logging.info(f"Validation - {row['source']}: {row['record_count']:,} records, "
                    f"{row['unique_months']} months, {row['unique_years']} years, "
                    f"dates: {row['min_date']} to {row['max_date']}")
        if row['completion_percentage']:
            logging.info(f"✅ Full load completion: {row['completion_percentage']}%")
    
    # Check if completion is satisfactory
    silver_result = [r for r in validation_results if r['source'] == 'silver'][0]
    if silver_result['completion_percentage'] and silver_result['completion_percentage'] >= 99.9:
        logging.info("🎉 Full load validation PASSED!")
    else:
        logging.warning("⚠️ Full load validation shows incomplete data transfer")
    
    return f"Validation complete: {silver_result['completion_percentage']}% of data transferred"

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

# Task 1: Check prerequisites and current state
check_prerequisites_task = PythonOperator(
    task_id='check_prerequisites',
    python_callable=check_prerequisites,
    dag=dag,
)

# Task 2: Estimate processing costs
estimate_costs_task = PythonOperator(
    task_id='estimate_costs',
    python_callable=estimate_costs,
    dag=dag,
)

# Task 3: Process full load in optimized batches
process_full_load_task = PythonOperator(
    task_id='process_full_load',
    python_callable=process_full_load_optimized,
    dag=dag,
)

# Task 4: Final validation
final_validation_task = PythonOperator(
    task_id='final_validation',
    python_callable=validate_full_load,
    dag=dag,
)

# Set up dependencies
check_prerequisites_task >> estimate_costs_task >> process_full_load_task >> final_validation_task 