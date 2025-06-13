#!/bin/bash

# Create Google Cloud connection
airflow connections add 'google_cloud_default' \
    --conn-type 'google_cloud_platform' \
    --conn-extra '{"project": "${project_id}", "key_path": "/opt/airflow/config/service-account.json"}'

# Create common Airflow variables
airflow variables set "gcp_project_id" "${project_id}"
airflow variables set "notification_email" '["admin@example.com"]'
airflow variables set "bigquery_location" "US"
airflow variables set "data_retention_days" "30"
airflow variables set "max_parallel_tasks" "5"
airflow variables set "environment" "dev" 