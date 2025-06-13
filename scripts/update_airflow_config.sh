#!/bin/bash

# Script to update Airflow configurations
# Usage: ./update_airflow_config.sh <component> <config_file>
# Example: ./update_airflow_config.sh scheduler airflow.cfg

set -e

COMPONENT=$1
CONFIG_FILE=$2
VM_NAME="airflow-vm"
PROJECT_ID=${DEV_GCP_PROJECT_ID}

# Get VM zone
VM_ZONE=$(gcloud compute instances list \
    --project=${PROJECT_ID} \
    --filter="name=${VM_NAME}" \
    --format='get(zone)' 2>/dev/null || echo 'NOT_FOUND')

if [ "$VM_ZONE" = "NOT_FOUND" ]; then
    echo "Error: Airflow VM not found"
    exit 1
fi

# Extract zone name from full path
VM_ZONE=$(echo $VM_ZONE | awk -F'/' '{print $NF}')

# Copy config file to VM
echo "Copying ${CONFIG_FILE} to VM..."
gcloud compute scp ${CONFIG_FILE} ${VM_NAME}:/tmp/$(basename ${CONFIG_FILE}) \
    --project=${PROJECT_ID} \
    --zone=${VM_ZONE}

# Update configuration based on component
case $COMPONENT in
    "scheduler")
        echo "Updating scheduler configuration..."
        gcloud compute ssh ${VM_NAME} \
            --project=${PROJECT_ID} \
            --zone=${VM_ZONE} \
            --command="sudo docker cp /tmp/$(basename ${CONFIG_FILE}) \$(sudo docker ps -q -f name=airflow-scheduler):/opt/airflow/airflow.cfg && sudo docker restart \$(sudo docker ps -q -f name=airflow-scheduler)"
        ;;
    "webserver")
        echo "Updating webserver configuration..."
        gcloud compute ssh ${VM_NAME} \
            --project=${PROJECT_ID} \
            --zone=${VM_ZONE} \
            --command="sudo docker cp /tmp/$(basename ${CONFIG_FILE}) \$(sudo docker ps -q -f name=airflow-webserver):/opt/airflow/airflow.cfg && sudo docker restart \$(sudo docker ps -q -f name=airflow-webserver)"
        ;;
    "worker")
        echo "Updating worker configuration..."
        gcloud compute ssh ${VM_NAME} \
            --project=${PROJECT_ID} \
            --zone=${VM_ZONE} \
            --command="sudo docker cp /tmp/$(basename ${CONFIG_FILE}) \$(sudo docker ps -q -f name=airflow-worker):/opt/airflow/airflow.cfg && sudo docker restart \$(sudo docker ps -q -f name=airflow-worker)"
        ;;
    *)
        echo "Error: Unknown component '$COMPONENT'"
        echo "Supported components: scheduler, webserver, worker"
        exit 1
        ;;
esac

echo "Configuration update completed for $COMPONENT" 