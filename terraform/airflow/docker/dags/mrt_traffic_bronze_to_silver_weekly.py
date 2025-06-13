from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryExecuteQueryOperator
from airflow.providers.google.cloud.sensors.bigquery import BigQueryTableExistenceSensor
from airflow.utils.dates import days_ago

# Import SQL queries from separate file
from sql.mrt_traffic_queries import (
    CHECK_NEW_DATA_QUERY,
    TRANSFORM_AND_LOAD_QUERY
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
    'retries': 1,
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

dag = DAG(
    'mrt_traffic_bronze_to_silver_weekly',
    default_args=default_args,
    description='Transfer and transform MRT traffic data from bronze to silver layer on a weekly basis',
    schedule_interval='0 10 * * 6',  # Run at 10 AM every Saturday
    start_date=days_ago(1),
    catchup=False,
    tags=['mrt', 'traffic', 'bronze', 'silver'],
    on_success_callback=notify_success,
    on_failure_callback=notify_failure
)

# Check if new data exists in bronze layer by comparing row counts
check_new_data = BigQueryExecuteQueryOperator(
    task_id='check_new_data',
    sql=CHECK_NEW_DATA_QUERY,
    use_legacy_sql=False,
    dag=dag,
)

# Transform and load data from bronze to silver
transform_and_load = BigQueryExecuteQueryOperator(
    task_id='transform_and_load',
    sql=TRANSFORM_AND_LOAD_QUERY,
    use_legacy_sql=False,
    dag=dag,
)

# Set task dependencies
check_new_data >> transform_and_load 