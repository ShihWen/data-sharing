#!/bin/bash

# Set bucket name
BUCKET_NAME="open-data-v2-cicd-airflow-storage"

# Create temporary directories
mkdir -p docker/config

# Copy files to temporary directory
cp ../terraform/airflow/docker/docker-compose.yml docker/
cp ../terraform/airflow/docker/config/airflow.cfg docker/config/

# Upload to GCS
gsutil -m cp -r docker/* gs://${BUCKET_NAME}/docker/

# Clean up
rm -rf docker/ 