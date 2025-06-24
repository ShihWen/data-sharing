#!/bin/bash

# Airflow Variables Configuration
# This script creates common Airflow variables used by DAGs

# Project-specific variables
airflow variables set "gcp_project_id" "${project_id}"
airflow variables set "gcp_region" "${region}"
airflow variables set "bigquery_location" "asia-east1"
airflow variables set "environment" "dev"

# Notification settings
airflow variables set "notification_email" '["admin@example.com"]'

# Data processing configuration
airflow variables set "data_retention_days" "30"
airflow variables set "max_parallel_tasks" "5"

# BigQuery dataset configurations
airflow variables set "bronze_dataset_suffix" "_bronze"
airflow variables set "silver_dataset_suffix" "_silver"
airflow variables set "gold_dataset_suffix" "_gold"

# Processing schedules
airflow variables set "default_retry_delay_minutes" "5"
airflow variables set "default_max_retries" "3"

# Data quality thresholds
airflow variables set "min_expected_records" "100"
airflow variables set "max_processing_hours" "24"

# Dataset configurations (used in SQL queries)
airflow variables set "tpe_mrt_bronze_dataset_id" "tpe_mrt_bronze"
airflow variables set "tpe_mrt_silver_dataset_id" "tpe_mrt_silver"
airflow variables set "tpe_mrt_gold_dataset_id" "tpe_mrt_gold"

# Datalake bucket
airflow variables set "gcs_data_lake_bucket" "open-data-v2-cicd-data-lake"

# Cloud Function URLs
airflow variables set "mrt_station_ntmc_function_uri" "https://asia-east1-open-data-v2-cicd.cloudfunctions.net/mrt-station-ntmc-fetcher"

echo "✅ All Airflow variables have been set successfully!" 