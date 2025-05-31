#!/bin/bash

# Airflow VM Restart Script
# This script safely restarts the Airflow VM and ensures services come up properly

set -e

echo "=== Airflow VM Restart Script ==="
echo "Timestamp: $(date)"
echo ""

# Configuration
PROJECT_ID="open-data-v2-cicd"
ZONE="asia-east1-b"
VM_NAME="airflow-vm"

# Function to check VM status
check_vm_status() {
    gcloud compute instances describe $VM_NAME --zone=$ZONE --format="get(status)" 2>/dev/null || echo "NOT_FOUND"
}

# Function to get VM IP
get_vm_ip() {
    gcloud compute instances describe $VM_NAME --zone=$ZONE --format="get(networkInterfaces[0].accessConfigs[0].natIP)" 2>/dev/null || echo ""
}

# Function to check Airflow health
check_airflow_health() {
    local vm_ip=$1
    if [ -z "$vm_ip" ]; then
        return 1
    fi
    curl -s --connect-timeout 10 "http://$vm_ip:8081/health" > /dev/null 2>&1
}

# Function to wait for VM to be running
wait_for_vm_running() {
    echo "Waiting for VM to be in RUNNING state..."
    local timeout=300
    while [ $timeout -gt 0 ]; do
        local status=$(check_vm_status)
        if [ "$status" = "RUNNING" ]; then
            echo "✅ VM is now RUNNING"
            return 0
        fi
        echo "VM status: $status, waiting... $(($timeout / 10)) checks remaining"
        sleep 10
        timeout=$((timeout - 10))
    done
    echo "❌ VM failed to reach RUNNING state within timeout"
    return 1
}

# Function to wait for Airflow to be healthy
wait_for_airflow_healthy() {
    local vm_ip=$1
    echo "Waiting for Airflow to be healthy..."
    local timeout=600  # 10 minutes for Airflow to fully start
    while [ $timeout -gt 0 ]; do
        if check_airflow_health "$vm_ip"; then
            echo "✅ Airflow is healthy!"
            return 0
        fi
        echo "Airflow not ready yet, waiting... $(($timeout / 30)) checks remaining"
        sleep 30
        timeout=$((timeout - 30))
    done
    echo "⚠️  Airflow health check timeout, but this may be normal during initial startup"
    return 1
}

# Main restart logic
echo "1️⃣ Checking current VM status..."
current_status=$(check_vm_status)
echo "Current VM status: $current_status"

if [ "$current_status" = "NOT_FOUND" ]; then
    echo "❌ VM not found! Please check if it exists."
    exit 1
fi

echo ""
echo "2️⃣ Stopping VM..."
if [ "$current_status" = "RUNNING" ]; then
    gcloud compute instances stop $VM_NAME --zone=$ZONE --quiet
    echo "VM stop command sent"
    
    # Wait for VM to stop
    echo "Waiting for VM to stop..."
    timeout=120
    while [ $timeout -gt 0 ]; do
        status=$(check_vm_status)
        if [ "$status" = "TERMINATED" ]; then
            echo "✅ VM is now stopped"
            break
        fi
        echo "VM status: $status, waiting..."
        sleep 5
        timeout=$((timeout - 5))
    done
else
    echo "VM is already stopped (status: $current_status)"
fi

echo ""
echo "3️⃣ Starting VM..."
gcloud compute instances start $VM_NAME --zone=$ZONE --quiet
echo "VM start command sent"

# Wait for VM to be running
if ! wait_for_vm_running; then
    echo "❌ Failed to start VM"
    exit 1
fi

echo ""
echo "4️⃣ Getting VM IP..."
vm_ip=$(get_vm_ip)
if [ -z "$vm_ip" ]; then
    echo "❌ Failed to get VM IP"
    exit 1
fi
echo "VM IP: $vm_ip"

echo ""
echo "5️⃣ Waiting for startup script to complete..."
echo "This may take several minutes as Docker containers are started..."

# Wait a bit for the startup script to begin
sleep 30

# Check startup script progress
echo "Monitoring startup script progress..."
for i in {1..20}; do
    echo "Check $i/20: Monitoring startup script..."
    
    # Check if startup script is still running
    startup_status=$(gcloud compute ssh $VM_NAME --zone=$ZONE --command="sudo systemctl is-active google-startup-scripts.service" 2>/dev/null || echo "unknown")
    echo "Startup script status: $startup_status"
    
    if [ "$startup_status" = "inactive" ]; then
        echo "Startup script has completed"
        break
    fi
    
    sleep 30
done

echo ""
echo "6️⃣ Checking Airflow services..."
# Wait for Airflow to be healthy
if wait_for_airflow_healthy "$vm_ip"; then
    echo ""
    echo "🎉 SUCCESS: Airflow VM restart completed successfully!"
    echo ""
    echo "🌐 Access Airflow UI: http://$vm_ip:8081"
    echo "👤 Username: admin"
    echo "🔑 Password: admin"
    echo ""
    echo "📋 Service status:"
    gcloud compute ssh $VM_NAME --zone=$ZONE --command="cd /opt/airflow && sudo docker-compose ps" 2>/dev/null || echo "Could not retrieve service status"
else
    echo ""
    echo "⚠️  Airflow restart completed but health check failed"
    echo "This may be normal during initial startup. Services may still be initializing."
    echo ""
    echo "🔧 Troubleshooting commands:"
    echo "• Check services: gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/airflow && sudo docker-compose ps'"
    echo "• Check logs: gcloud compute ssh $VM_NAME --zone=$ZONE --command='cd /opt/airflow && sudo docker-compose logs airflow-webserver --tail=20'"
    echo "• Check startup logs: gcloud compute ssh $VM_NAME --zone=$ZONE --command='sudo journalctl -u google-startup-scripts.service --no-pager | tail -50'"
    echo ""
    echo "🌐 Try accessing: http://$vm_ip:8081"
fi

echo ""
echo "=== Restart Summary ==="
echo "VM Status: $(check_vm_status)"
echo "VM IP: $vm_ip"
echo "Timestamp: $(date)" 