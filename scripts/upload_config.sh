#!/bin/bash

# Set bucket name
BUCKET_NAME="open-data-v2-cicd-airflow-storage"

# Copy files to temporary directory
cp -r ../terraform/airflow/docker docker/

# Upload to GCS
gsutil -m cp -r docker/* gs://${BUCKET_NAME}/docker/

# Clean up
rm -rf docker/

echo "Successfully uploaded Airflow configuration to gs://${BUCKET_NAME}/docker/" 