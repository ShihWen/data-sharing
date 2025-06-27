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

echo "1️⃣ Uploading scripts to GCS..."
if [ -f "./airflow-manager.sh" ]; then
    print_info "Found airflow-manager.sh script locally, uploading to GCS..."
    gsutil cp ./airflow-manager.sh gs://$BUCKET_NAME/scripts/airflow-manager.sh
    print_status "Uploaded airflow-manager.sh to GCS"
else
    print_error "airflow-manager.sh script not found in current directory"
    print_info "Please run this script from the scripts/ directory"
    exit 1
fi

if [ -f "../terraform/airflow/templates/airflow_dags" ]; then
    print_info "Found airflow_dags configuration, uploading to GCS..."
    gsutil cp ../terraform/airflow/templates/airflow_dags gs://$BUCKET_NAME/scripts/airflow_dags
    print_status "Uploaded airflow_dags to GCS"
else
    print_warning "airflow_dags file not found at ../terraform/airflow/templates/airflow_dags"
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
set -ex

echo "========== Starting Airflow Auto Setup: $(date) =========="

PROJECT_ID="open-data-v2-cicd"
BUCKET_NAME="open-data-v2-cicd-airflow-storage"
AIRFLOW_UID=50000
LOG_FILE="/opt/airflow/logs/auto_setup.log"

# Ensure log file exists and has correct permissions
mkdir -p /opt/airflow/logs
# Truncate log file to keep it from growing indefinitely
cat /dev/null > $LOG_FILE
chown $AIRFLOW_UID:root $LOG_FILE

# Ensure we are in the right directory
cd /opt/airflow || { echo "ERROR: Could not cd to /opt/airflow" >> $LOG_FILE; exit 1; }

# Download latest scripts
echo "Downloading airflow-manager.sh from GCS..." >> $LOG_FILE
gsutil cp gs://$BUCKET_NAME/scripts/airflow-manager.sh ./airflow-manager.sh
chmod +x ./airflow-manager.sh
chown $AIRFLOW_UID:root ./airflow-manager.sh

echo "Downloading airflow_dags from GCS..." >> $LOG_FILE
gsutil cp gs://$BUCKET_NAME/scripts/airflow_dags ./airflow_dags || echo "*" > ./airflow_dags
chown $AIRFLOW_UID:root ./airflow_dags

# Wait for Airflow to be healthy
echo "Waiting for Airflow health check..." >> $LOG_FILE
timeout=600 # 10 minutes
while [ $timeout -gt 0 ]; do
    if curl -s --fail --connect-timeout 5 "http://localhost:8081/health" > /dev/null 2>&1; then
        echo "Airflow is ready!" >> $LOG_FILE
        break
    fi
    echo "Waiting for Airflow... $(($timeout / 10))s remaining" >> $LOG_FILE
    sleep 10
    timeout=$(($timeout - 10))
done

if [ $timeout -le 0 ]; then
    echo "ERROR: Airflow did not become healthy in time." >> $LOG_FILE
    exit 1
fi

sleep 15 # Extra wait time for services to be fully responsive

# Run setup using airflow-manager
echo "Running connections setup..." >> $LOG_FILE
./airflow-manager.sh connections-internal >> $LOG_FILE 2>&1

echo "Unpausing DAGs..." >> $LOG_FILE
./airflow-manager.sh unpause_dags >> $LOG_FILE 2>&1

echo "========== Airflow Auto Setup Finished Successfully: $(date) ==========" >> $LOG_FILE
EOF

echo "DEBUG: About to copy the setup script to the VM. The next lines will show the exact commands being run."
set -x

# Copy the new setup script to the VM by staging it in /tmp first
gcloud compute scp /tmp/setup_auto_connections.sh $VM_NAME:/tmp/auto_setup.sh --zone=$ZONE
gcloud compute ssh $VM_NAME --zone=$ZONE --command="sudo mv /tmp/auto_setup.sh /opt/airflow/auto_setup.sh && sudo chmod +x /opt/airflow/auto_setup.sh && sudo chown root:root /opt/airflow/auto_setup.sh"

set +x

# Create a new, more robust systemd service on the VM
cat > /tmp/airflow-auto-setup.service <<'SERVICE_EOF'
[Unit]
Description=Airflow Automatic Connections, Variables and DAGs Setup
Wants=airflow-startup.service
After=airflow-startup.service network-online.target

[Service]
Type=oneshot
User=root
ExecStart=/opt/airflow/auto_setup.sh

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Upload the service file and set it up
gcloud compute scp /tmp/airflow-auto-setup.service $VM_NAME:/tmp/airflow-auto-setup.service --zone=$ZONE

gcloud compute ssh $VM_NAME --zone=$ZONE <<'REMOTE_EOF'
set -e
echo "Configuring new systemd service..."

# Remove old service if it exists
if [ -f /etc/systemd/system/airflow-connections.service ]; then
    echo "Removing old airflow-connections.service..."
    sudo systemctl stop airflow-connections.service || true
    sudo systemctl disable airflow-connections.service || true
    sudo rm -f /etc/systemd/system/airflow-connections.service
fi

sudo mv /tmp/airflow-auto-setup.service /etc/systemd/system/airflow-auto-setup.service
sudo chown root:root /etc/systemd/system/airflow-auto-setup.service
sudo systemctl daemon-reload
sudo systemctl enable airflow-auto-setup.service

echo "✅ New auto-setup service enabled"

echo "Testing the new service..."
sudo systemctl start airflow-auto-setup.service
echo "✅ Service started. Check logs for details: /opt/airflow/logs/auto_setup.log"
REMOTE_EOF


echo ""
echo "4️⃣ Testing the setup..."
print_info "Checking service status on VM..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="sudo systemctl status airflow-auto-setup.service --no-pager" || true

echo ""
print_info "Displaying the last 20 lines of the new log file..."
gcloud compute ssh $VM_NAME --zone=$ZONE --command="tail -n 20 /opt/airflow/logs/auto_setup.log" || echo "Log file not found or empty."


echo ""
echo "5️⃣ Cleanup..."
rm -f /tmp/setup_auto_connections.sh /tmp/airflow-auto-setup.service

echo ""
print_status "🎉 SUCCESS: Auto-connections setup completed with new robust service!"
echo ""
echo "📋 What was configured:"
echo "   ✅ Uploaded a new robust 'auto_setup.sh' script to the VM"
echo "   ✅ Removed the old 'airflow-connections.service'"
echo "   ✅ Created and enabled a new 'airflow-auto-setup.service' to run the script on startup"
echo "   ✅ All logs from the auto-setup process are now in /opt/airflow/logs/auto_setup.log on the VM"
echo ""
echo "Next Steps:"
echo "   1. RESTART your Airflow VM from the GCP console."
echo "   2. After a few minutes, check if the connections, variables, and DAGs are correctly set up."
echo "   3. If it still doesn't work, check the log file for errors:"
echo "      gcloud compute ssh $VM_NAME --zone=$ZONE --command=\"cat /opt/airflow/logs/auto_setup.log\""
echo ""
echo "🌐 Access Airflow: http://$VM_IP:8081"
echo "👤 Username: admin"
echo "�� Password: admin" 