#!/bin/bash

# Set bucket name
BUCKET_NAME="open-data-v2-cicd-airflow-storage"

# Set source directory for DAGs
SOURCE_DIR="../terraform/airflow/docker/dags"
DESTINATION="gs://${BUCKET_NAME}/docker/dags/"

# Check if source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "Error: Source directory $SOURCE_DIR does not exist"
    exit 1
fi

# Sync DAGs to GCS - this will add, update, and delete files as needed
echo "Syncing DAGs from $SOURCE_DIR to $DESTINATION"
gsutil -m rsync -r -d "$SOURCE_DIR" "$DESTINATION"

# The -d flag enables deletion of files in destination that don't exist in source
# The -r flag enables recursive sync
# The -m flag enables parallel uploads for better performance

echo "Successfully synced Airflow DAGs to $DESTINATION"
echo "Files added, updated, and deleted as necessary to match local state" 