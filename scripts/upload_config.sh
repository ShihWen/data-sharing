#!/bin/bash

# Create temporary directories
mkdir -p docker/config

# Copy files to temporary directory
cp docker-compose.yml docker/
cp config/airflow.cfg docker/config/

# Upload to GCS
gsutil -m cp -r docker/* gs://open-data-v2-cicd-airflow-storage/docker/

# Clean up
rm -rf docker/ 