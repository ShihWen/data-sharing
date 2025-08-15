#!/bin/bash

# Upload airflow-manager.sh to GCS bucket for VM startup script
# This ensures the startup script can download and use the full script instead of the fallback

set -e

echo "=== Uploading airflow-manager.sh to GCS ==="

# Configuration
BUCKET_NAME="open-data-v2-cicd-airflow-storage"
SCRIPT_PATH="./airflow-manager.sh"
GCS_DESTINATION="gs://${BUCKET_NAME}/scripts/airflow-manager.sh"

# Check if airflow-manager.sh exists locally
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "ERROR: $SCRIPT_PATH not found in current directory"
    echo "Please run this script from the scripts/ directory"
    exit 1
fi

# Check if gsutil is available
if ! command -v gsutil &> /dev/null; then
    echo "ERROR: gsutil command not found"
    echo "Please install Google Cloud SDK or authenticate with gcloud"
    exit 1
fi

echo "📤 Uploading $SCRIPT_PATH to $GCS_DESTINATION..."

# Upload the script
if gsutil cp "$SCRIPT_PATH" "$GCS_DESTINATION"; then
    echo "SUCCESS: Successfully uploaded airflow-manager.sh to GCS"
    echo "The startup script will now be able to download and use the full script"
    echo ""
    echo "Next steps:"
    echo "1. Restart your Airflow VM to test the new startup script"
    echo "2. The startup script will now create all connections and variables automatically"
else
    echo "ERROR: Failed to upload airflow-manager.sh to GCS"
    exit 1
fi

echo ""
echo "SUCCESS: Upload complete! Your Airflow VM will now have access to the full script on next restart."
