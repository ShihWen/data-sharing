#!/bin/bash

# Create Google Cloud connection
airflow connections add 'google_cloud_default' \
    --conn-type 'google_cloud_platform' \
    --conn-extra '{"project": "${project_id}", "key_path": "/opt/airflow/config/gcp-key.json"}' 