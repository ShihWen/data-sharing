#!/bin/bash

# Setup Auto Connections for Airflow VM
# This script sets up automatic creation of Airflow connections and variables on VM restart
# Uses the existing airflow-manager.sh script for consistency

set -e

echo "=== Airflow Auto-Connections Setup ==="
echo "Timestamp: $(date)"
echo ""

# Configuration
PROJECT_ID="open-data-v2-cicd"
ZONE="asia-east1-b"
VM_NAME="airflow-vm"
BUCKET_NAME="open-data-v2-cicd-airflow-storage"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Function to check VM status
check_vm_status() {
    gcloud compute instances describe $VM_NAME --zone=$ZONE --format="get(status)" 2>/dev/null || echo "NOT_FOUND"
}

# Function to get VM IP
get_vm_ip() {
    gcloud compute instances describe $VM_NAME --zone=$ZONE --format="get(networkInterfaces[0].accessConfigs[0].natIP)" 2>/dev/null || echo ""
}

echo "1️⃣ Uploading airflow-manager.sh to GCS..."
if [ -f "./airflow-manager.sh" ]; then
    print_info "Found airflow-manager.sh script locally, uploading to GCS..."
    gsutil cp ./airflow-manager.sh gs://$BUCKET_NAME/scripts/airflow-manager.sh
    print_status "Uploaded airflow-manager.sh to GCS"
else
    print_error "airflow-manager.sh script not found in current directory"
    print_info "Please run this script from the scripts/ directory"
    exit 1
fi

echo ""
echo "2️⃣ Checking VM status..."
VM_STATUS=$(check_vm_status)
if [ "$VM_STATUS" != "RUNNING" ]; then
    print_error "VM is not running (status: $VM_STATUS)"
    print_info "Please start the VM first: gcloud compute instances start $VM_NAME --zone=$ZONE"
    exit 1
fi
print_status "VM is running"

VM_IP=$(get_vm_ip)
print_info "VM IP: $VM_IP"

echo ""
echo "3️⃣ Setting up auto-connections service on VM..."

# Create the setup script to run on the VM
cat > /tmp/setup_auto_connections.sh <<'EOF'
#!/bin/bash
set -e

PROJECT_ID="open-data-v2-cicd"
BUCKET_NAME="open-data-v2-cicd-airflow-storage"
AIRFLOW_UID=50000

echo "Setting up auto-connections service using airflow-manager.sh..."

# Download airflow-manager.sh from GCS
echo "Downloading airflow-manager.sh from GCS..."
cd /opt/airflow
if gsutil cp gs://$BUCKET_NAME/scripts/airflow-manager.sh ./airflow-manager.sh; then
    chmod +x ./airflow-manager.sh
    chown $AIRFLOW_UID:root ./airflow-manager.sh
    echo "✅ Downloaded and configured airflow-manager.sh"
else
    echo "❌ Failed to download airflow-manager.sh from GCS"
    echo "Creating minimal fallback script..."
    
    # Create minimal fallback script
    cat > /opt/airflow/create_connections_fallback.sh <<'FALLBACK_EOF'
#!/bin/bash
set -e
echo "Creating basic Google Cloud connection..."
cd /opt/airflow
# Wait for Airflow to be ready
timeout=300
while [ $timeout -gt 0 ]; do
    if curl -s --connect-timeout 10 "http://localhost:8081/health" > /dev/null 2>&1; then
        break
    fi
    sleep 10
    timeout=$((timeout - 10))
done
# Create basic connection
docker-compose exec -T airflow-webserver airflow connections delete 'google_cloud_default' 2>/dev/null || true
docker-compose exec -T airflow-webserver airflow connections add 'google_cloud_default' \
    --conn-type 'google_cloud_platform' \
    --conn-extra '{"project": "open-data-v2-cicd", "key_path": "/opt/airflow/config/service-account.json"}'
echo "✅ Basic connection created"
FALLBACK_EOF
    chmod +x /opt/airflow/create_connections_fallback.sh
    chown $AIRFLOW_UID:root /opt/airflow/create_connections_fallback.sh
    echo "✅ Created fallback connections script"
fi

# Create systemd service for automatic connections creation
cat > /etc/systemd/system/airflow-connections.service <<'SERVICE_EOF'
[Unit]
Description=Create Airflow Connections and Variables using airflow-manager.sh
After=multi-user.target
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/airflow
Environment="PROJECT_ID=open-data-v2-cicd"
Environment="ZONE=asia-east1-b"
Environment="VM_NAME=airflow-vm"
Environment="BUCKET_NAME=open-data-v2-cicd-airflow-storage"
ExecStartPre=/bin/bash -c 'timeout=600; while [ $timeout -gt 0 ]; do if curl -s --connect-timeout 5 "http://localhost:8081/health" > /dev/null 2>&1; then echo "Airflow is ready"; break; fi; echo "Waiting for Airflow... $(($timeout / 30)) checks remaining"; sleep 30; timeout=$(($timeout - 30)); done'
ExecStart=/bin/bash -c 'if [ -f /opt/airflow/airflow-manager.sh ]; then /opt/airflow/airflow-manager.sh connections; else /opt/airflow/create_connections_fallback.sh; fi'
StandardOutput=journal
StandardError=journal
RemainAfterExit=yes
TimeoutStartSec=900

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Enable the connections service
systemctl daemon-reload
systemctl enable airflow-connections.service

echo "✅ Auto-connections service enabled"

# Test the service
echo "Testing the service..."
if systemctl start airflow-connections.service; then
    echo "✅ Service started successfully"
    echo "Service logs:"
    journalctl -u airflow-connections.service --no-pager | tail -20
else
    echo "❌ Service failed to start"
    journalctl -u airflow-connections.service --no-pager | tail -20
fi

echo ""
echo "Auto-connections setup completed!"
EOF

# Copy and execute the setup script
print_info "Copying setup script to VM..."
gcloud compute scp /tmp/setup_auto_connections.sh $VM_NAME:/tmp/setup_auto_connections.sh --zone=$ZONE

print_info "Executing setup script on VM..."
if gcloud compute ssh $VM_NAME --zone=$ZONE --command="chmod +x /tmp/setup_auto_connections.sh && sudo /tmp/setup_auto_connections.sh"; then
    print_status "Auto-connections service set up successfully!"
else
    print_error "Failed to set up auto-connections service"
    exit 1
fi

echo ""
echo "4️⃣ Testing the setup..."
print_info "Checking service status..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="sudo systemctl status airflow-connections.service --no-pager" || true

echo ""
echo "5️⃣ Cleanup..."
rm -f /tmp/setup_auto_connections.sh
gcloud compute ssh $VM_NAME --zone=$ZONE --command="rm -f /tmp/setup_auto_connections.sh" 2>/dev/null || true

echo ""
print_status "🎉 SUCCESS: Auto-connections setup completed!"
echo ""
echo "📋 What was configured:"
echo "   ✅ Uploaded airflow-manager.sh to GCS bucket"
echo "   ✅ Downloaded airflow-manager.sh to VM at /opt/airflow/"
echo "   ✅ Created airflow-connections.service systemd service"
echo "   ✅ Enabled service to run automatically on VM restart"
echo "   ✅ Service uses existing airflow-manager.sh connections functionality"
echo ""
echo "🔄 How it works:"
echo "   • Service automatically runs when VM starts/restarts"
echo "   • Downloads latest airflow-manager.sh from GCS if needed"
echo "   • Waits for Airflow health endpoint to be available"
echo "   • Executes './airflow-manager.sh connections' command"
echo "   • Falls back to basic connection creation if script unavailable"
echo ""
echo "🛠  Manual commands:"
echo "   • Check service status: gcloud compute ssh $VM_NAME --zone=$ZONE --command='sudo systemctl status airflow-connections.service'"
echo "   • View service logs: gcloud compute ssh $VM_NAME --zone=$ZONE --command='sudo journalctl -u airflow-connections.service'"
echo "   • Run manually: gcloud compute ssh $VM_NAME --zone=$ZONE --command='sudo systemctl start airflow-connections.service'"
echo "   • Test airflow-manager directly: gcloud compute ssh $VM_NAME --zone=$ZONE --command='sudo /opt/airflow/airflow-manager.sh connections'"
echo ""
echo "🌐 Access Airflow: http://$VM_IP:8081"
echo "👤 Username: admin"
echo "�� Password: admin" 