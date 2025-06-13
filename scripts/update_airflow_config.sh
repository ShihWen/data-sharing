#!/bin/bash

# Script to update Airflow configurations
# Usage: ./update_airflow_config.sh <component> <config_file>
# Example: ./update_airflow_config.sh scheduler airflow.cfg

set -e

COMPONENT=$1
CONFIG_FILE=$2
VM_NAME="airflow-vm"
PROJECT_ID=${DEV_GCP_PROJECT_ID}

# Function to wait for Docker to be ready
wait_for_docker() {
    echo "Waiting for Docker to be available on VM..."
    local max_wait=300  # 5 minutes
    local wait_time=0
    
    while [ $wait_time -lt $max_wait ]; do
        if gcloud compute ssh ${VM_NAME} \
            --project=${PROJECT_ID} \
            --zone=${VM_ZONE} \
            --command="sudo docker --version" >/dev/null 2>&1; then
            echo "✅ Docker is available!"
            return 0
        fi
        
        echo "⏳ Waiting for Docker... (${wait_time}/${max_wait} seconds)"
        sleep 10
        wait_time=$((wait_time + 10))
    done
    
    echo "❌ Docker not available after ${max_wait} seconds"
    return 1
}

# Function to wait for Airflow containers
wait_for_airflow_containers() {
    echo "Waiting for Airflow containers to be running..."
    local max_wait=300  # 5 minutes
    local wait_time=0
    
    while [ $wait_time -lt $max_wait ]; do
        local container_count=$(gcloud compute ssh ${VM_NAME} \
            --project=${PROJECT_ID} \
            --zone=${VM_ZONE} \
            --command="sudo docker ps -q -f name=airflow | wc -l" 2>/dev/null || echo "0")
        
        if [ "$container_count" -ge "2" ]; then
            echo "✅ Airflow containers are running! (${container_count} containers)"
            return 0
        fi
        
        echo "⏳ Waiting for Airflow containers... (${wait_time}/${max_wait} seconds, found ${container_count} containers)"
        sleep 10
        wait_time=$((wait_time + 10))
    done
    
    echo "❌ Airflow containers not ready after ${max_wait} seconds"
    return 1
}

echo "=== Airflow Configuration Update ==="
echo "Component: $COMPONENT"
echo "Config File: $CONFIG_FILE"
echo "VM: $VM_NAME"
echo "Project: $PROJECT_ID"
echo ""

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: Config file '$CONFIG_FILE' not found"
    exit 1
fi

# Get VM zone
echo "🔍 Finding VM zone..."
VM_ZONE=$(gcloud compute instances list \
    --project=${PROJECT_ID} \
    --filter="name=${VM_NAME}" \
    --format='get(zone)' 2>/dev/null || echo 'NOT_FOUND')

if [ "$VM_ZONE" = "NOT_FOUND" ]; then
    echo "❌ Error: Airflow VM not found"
    exit 1
fi

# Extract zone name from full path
VM_ZONE=$(echo $VM_ZONE | awk -F'/' '{print $NF}')
echo "✅ Found VM in zone: $VM_ZONE"

# Check VM status
echo ""
echo "🔍 Checking VM status..."
VM_STATUS=$(gcloud compute instances describe ${VM_NAME} \
    --project=${PROJECT_ID} \
    --zone=${VM_ZONE} \
    --format='get(status)' 2>/dev/null || echo 'UNKNOWN')

echo "VM Status: $VM_STATUS"

if [ "$VM_STATUS" != "RUNNING" ]; then
    echo "❌ Error: VM is not running (status: $VM_STATUS)"
    exit 1
fi

# Wait for Docker to be ready
echo ""
if ! wait_for_docker; then
    echo "❌ Failed to wait for Docker"
    exit 1
fi

# Wait for Airflow containers
echo ""
if ! wait_for_airflow_containers; then
    echo "❌ Failed to wait for Airflow containers"
    exit 1
fi

# Copy config file to VM
echo ""
echo "📁 Copying ${CONFIG_FILE} to VM..."
gcloud compute scp ${CONFIG_FILE} ${VM_NAME}:/tmp/$(basename ${CONFIG_FILE}) \
    --project=${PROJECT_ID} \
    --zone=${VM_ZONE}

echo "✅ Config file copied successfully"

# Update configuration based on component
echo ""
echo "🔧 Updating $COMPONENT configuration..."

case $COMPONENT in
    "scheduler")
        echo "Updating scheduler configuration..."
        gcloud compute ssh ${VM_NAME} \
            --project=${PROJECT_ID} \
            --zone=${VM_ZONE} \
            --command="
                # Find scheduler container ID
                SCHEDULER_ID=\$(sudo docker ps -q -f name=airflow-scheduler)
                if [ -z \"\$SCHEDULER_ID\" ]; then
                    echo '❌ Scheduler container not found'
                    exit 1
                fi
                echo \"✅ Found scheduler container: \$SCHEDULER_ID\"
                
                # Copy config and restart
                sudo docker cp /tmp/$(basename ${CONFIG_FILE}) \$SCHEDULER_ID:/opt/airflow/airflow.cfg
                echo '✅ Config file copied to container'
                
                sudo docker restart \$SCHEDULER_ID
                echo '✅ Scheduler container restarted'
            "
        ;;
    "webserver")
        echo "Updating webserver configuration..."
        gcloud compute ssh ${VM_NAME} \
            --project=${PROJECT_ID} \
            --zone=${VM_ZONE} \
            --command="
                # Find webserver container ID
                WEBSERVER_ID=\$(sudo docker ps -q -f name=airflow-webserver)
                if [ -z \"\$WEBSERVER_ID\" ]; then
                    echo '❌ Webserver container not found'
                    exit 1
                fi
                echo \"✅ Found webserver container: \$WEBSERVER_ID\"
                
                # Copy config and restart
                sudo docker cp /tmp/$(basename ${CONFIG_FILE}) \$WEBSERVER_ID:/opt/airflow/airflow.cfg
                echo '✅ Config file copied to container'
                
                sudo docker restart \$WEBSERVER_ID
                echo '✅ Webserver container restarted'
            "
        ;;
    "worker")
        echo "Updating worker configuration..."
        gcloud compute ssh ${VM_NAME} \
            --project=${PROJECT_ID} \
            --zone=${VM_ZONE} \
            --command="
                # Find worker container ID
                WORKER_ID=\$(sudo docker ps -q -f name=airflow-worker)
                if [ -z \"\$WORKER_ID\" ]; then
                    echo '❌ Worker container not found'
                    exit 1
                fi
                echo \"✅ Found worker container: \$WORKER_ID\"
                
                # Copy config and restart
                sudo docker cp /tmp/$(basename ${CONFIG_FILE}) \$WORKER_ID:/opt/airflow/airflow.cfg
                echo '✅ Config file copied to container'
                
                sudo docker restart \$WORKER_ID
                echo '✅ Worker container restarted'
            "
        ;;
    *)
        echo "❌ Error: Unknown component '$COMPONENT'"
        echo "Supported components: scheduler, webserver, worker"
        exit 1
        ;;
esac

# Cleanup temp file
echo ""
echo "🧹 Cleaning up..."
gcloud compute ssh ${VM_NAME} \
    --project=${PROJECT_ID} \
    --zone=${VM_ZONE} \
    --command="rm -f /tmp/$(basename ${CONFIG_FILE})" || true

echo ""
echo "✅ Configuration update completed successfully for $COMPONENT!"
echo "🎯 The $COMPONENT container has been restarted with the new configuration." 