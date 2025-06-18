from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryExecuteQueryOperator
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.utils.dates import days_ago
from airflow.models import Variable
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

# Get the location at module level to use in operators
BIGQUERY_LOCATION = Variable.get('bigquery_location', 'asia-east1')

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=3),
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

def check_prerequisites_with_hook(**context):
    """
    Check prerequisites using BigQuery hook with proper location handling.
    """
    # Get variables using Airflow's Variable model
    project_id = Variable.get('project_id')
    location = Variable.get('bigquery_location', 'asia-east1')
    
    logging.info(f"🌏 Using BigQuery location: {location}")
    logging.info(f"📊 Using project: {project_id}")
    
    hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False,
        location=location
    )
    
    # Render the SQL template
    bronze_dataset = Variable.get('tpe_mrt_bronze_dataset_id')
    silver_dataset = Variable.get('tpe_mrt_silver_dataset_id')
    
    rendered_sql = CHECK_PREREQUISITES_QUERY.replace(
        '{{ var.value.project_id }}', project_id
    ).replace(
        '{{ var.value.tpe_mrt_bronze_dataset_id }}', bronze_dataset
    ).replace(
        '{{ var.value.tpe_mrt_silver_dataset_id }}', silver_dataset
    )
    
    logging.info("🔍 Executing prerequisites check query...")
    
    job_config = {
        'query': {
            'query': rendered_sql,
            'useLegacySql': False
        }
    }
    
    query_job = hook.insert_job(
        configuration=job_config,
        project_id=project_id,
        location=location
    )
    
    results = query_job.result()
    result = list(results)[0]
    
    logging.info(f"Prerequisites check results:")
    logging.info(f"Bronze: {result['bronze_records']} records, {result['bronze_months']} months")
    logging.info(f"Silver: {result['silver_records']} records, {result['silver_months']} months")
    logging.info(f"Status: {result['load_status']}")
    
    if result['load_status'] == 'ALREADY_COMPLETE':
        raise Exception("Full load already complete! Silver table has same record count as bronze.")
    
    # Store info for downstream tasks
    context['task_instance'].xcom_push(key='load_info', value=dict(result))
    
    return f"Ready for full load: {result['load_status']}"

def estimate_costs_with_hook(**context):
    """
    Estimate costs using BigQuery hook with proper location handling.
    """
    # Get variables
    project_id = Variable.get('project_id')
    location = Variable.get('bigquery_location', 'asia-east1')
    bronze_dataset = Variable.get('tpe_mrt_bronze_dataset_id')
    
    logging.info(f"🌏 Using BigQuery location: {location}")
    
    hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False,
        location=location
    )
    
    # Render the SQL template
    rendered_sql = COST_ESTIMATION_QUERY.replace(
        '{{ var.value.project_id }}', project_id
    ).replace(
        '{{ var.value.tpe_mrt_bronze_dataset_id }}', bronze_dataset
    )
    
    logging.info("💰 Executing cost estimation query...")
    
    job_config = {
        'query': {
            'query': rendered_sql,
            'useLegacySql': False
        }
    }
    
    query_job = hook.insert_job(
        configuration=job_config,
        project_id=project_id,
        location=location
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

def process_full_load_years(**context):
    """
    Coordinate the year-by-year processing.
    Since we need to process multiple years, we'll do this in a loop.
    """
    # Get variables using Airflow's Variable model for proper resolution
    hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False,
        location=Variable.get('bigquery_location', 'asia-east1')
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
        
        # Wait for the job to complete
        query_job.result()  # This waits for completion
        
        # Get the number of affected rows from the job object, not the result
        rows_processed = 0
        
        # Try multiple ways to get the affected row count
        try:
            # Method 1: Direct attribute access
            if hasattr(query_job, 'num_dml_affected_rows') and query_job.num_dml_affected_rows is not None:
                rows_processed = query_job.num_dml_affected_rows
                logging.info(f"📊 Got row count from num_dml_affected_rows: {rows_processed}")
            
            # Method 2: From job statistics
            elif hasattr(query_job, 'statistics') and query_job.statistics:
                stats = query_job.statistics
                if hasattr(stats, 'num_dml_affected_rows') and stats.num_dml_affected_rows is not None:
                    rows_processed = stats.num_dml_affected_rows
                    logging.info(f"📊 Got row count from statistics.num_dml_affected_rows: {rows_processed}")
            
            # Method 3: From job configuration/state
            elif hasattr(query_job, '_properties') and query_job._properties:
                props = query_job._properties
                if 'statistics' in props and 'numDmlAffectedRows' in props['statistics']:
                    rows_processed = int(props['statistics']['numDmlAffectedRows'])
                    logging.info(f"📊 Got row count from _properties.statistics: {rows_processed}")
            
            # If we still don't have a count, log available attributes for debugging
            if rows_processed == 0:
                logging.warning(f"⚠️ Could not determine affected row count for year {year}")
                logging.info(f"Available query_job attributes: {[attr for attr in dir(query_job) if not attr.startswith('_')]}")
                if hasattr(query_job, 'statistics'):
                    logging.info(f"Statistics attributes: {[attr for attr in dir(query_job.statistics) if not attr.startswith('_')]}")
                
                # Set a default based on typical year processing
                rows_processed = 0  # We'll track this as 0 but job still succeeded
                
        except Exception as e:
            logging.warning(f"⚠️ Error getting row count for year {year}: {e}")
            rows_processed = 0
        
        total_processed += rows_processed
        
        logging.info(f"✅ Year {year} completed: {rows_processed:,} records processed in {location}")
    
    logging.info(f"🎉 Full load completed: {total_processed:,} total records processed")
    
    # Store processing info
    context['task_instance'].xcom_push(key='processing_results', value={
        'total_processed': total_processed,
        'years_processed': len(years_to_process)
    })
    
    return f"Processed {total_processed:,} records across {len(years_to_process)} years"

def validate_full_load_with_hook(**context):
    """
    Validate the full load results using BigQuery hook.
    """
    # Get variables
    project_id = Variable.get('project_id')
    location = Variable.get('bigquery_location', 'asia-east1')
    bronze_dataset = Variable.get('tpe_mrt_bronze_dataset_id')
    silver_dataset = Variable.get('tpe_mrt_silver_dataset_id')
    
    logging.info(f"🌏 Using BigQuery location: {location}")
    
    hook = BigQueryHook(
        gcp_conn_id='google_cloud_default',
        use_legacy_sql=False,
        location=location
    )
    
    # Render the SQL template
    rendered_sql = FULL_LOAD_VALIDATION_QUERY.replace(
        '{{ var.value.project_id }}', project_id
    ).replace(
        '{{ var.value.tpe_mrt_bronze_dataset_id }}', bronze_dataset
    ).replace(
        '{{ var.value.tpe_mrt_silver_dataset_id }}', silver_dataset
    )
    
    logging.info("🔍 Executing validation query...")
    
    job_config = {
        'query': {
            'query': rendered_sql,
            'useLegacySql': False
        }
    }
    
    query_job = hook.insert_job(
        configuration=job_config,
        project_id=project_id,
        location=location
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
    tags=['mrt', 'traffic', 'full-load', 'bronze', 'silver'],
    on_success_callback=notify_success,
    on_failure_callback=notify_failure,
    max_active_runs=1
)

# Task 1: Check prerequisites using Python function with proper location
check_prerequisites_task = PythonOperator(
    task_id='check_prerequisites',
    python_callable=check_prerequisites_with_hook,
    dag=dag,
)

# Task 2: Estimate costs using Python function with proper location
estimate_costs_task = PythonOperator(
    task_id='estimate_costs',
    python_callable=estimate_costs_with_hook,
    dag=dag,
)

# Task 3: Process full load in optimized batches
process_full_load_task = PythonOperator(
    task_id='process_full_load',
    python_callable=process_full_load_years,
    dag=dag,
)

# Task 4: Final validation using Python function with proper location
final_validation_task = PythonOperator(
    task_id='final_validation',
    python_callable=validate_full_load_with_hook,
    dag=dag,
)

# Set up dependencies
check_prerequisites_task >> estimate_costs_task >> process_full_load_task >> final_validation_task 