from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.bigquery import BigQueryExecuteQueryOperator
import os

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def print_hello():
    """Print hello as a test task"""
    print('Hello from Airflow!')
    return 'Hello from Airflow!'

with DAG(
    'example_dag',
    default_args=default_args,
    description='A simple example DAG with BigQuery integration',
    schedule_interval='0 12 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['example'],
) as dag:

    start = EmptyOperator(
        task_id='start',
    )

    hello_task = PythonOperator(
        task_id='hello_task',
        python_callable=print_hello,
    )

    # Example BigQuery task
    bq_task = BigQueryExecuteQueryOperator(
        task_id='example_bq_query',
        sql='''
            SELECT 
                CURRENT_TIMESTAMP() as execution_time,
                'Hello from BigQuery' as message
        ''',
        use_legacy_sql=False,
        location='asia-east1',
        gcp_conn_id='google_cloud_default'
    )

    end = EmptyOperator(
        task_id='end',
    )

    # Define task dependencies
    start >> hello_task >> bq_task >> end 