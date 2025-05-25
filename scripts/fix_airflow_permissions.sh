#!/bin/bash

# Fix Airflow Permissions Script
# This script fixes the user/permission issues on the existing Airflow VM

set -e

echo "=== Fixing Airflow Permissions ==="
echo "Timestamp: $(date)"
echo ""

# Check if VM is running
VM_STATUS=$(gcloud compute instances describe airflow-vm --zone=asia-east1-b --format="get(status)" 2>/dev/null || echo "NOT_FOUND")

if [ "$VM_STATUS" != "RUNNING" ]; then
    echo "❌ ERROR: Airflow VM is not running (status: $VM_STATUS)"
    echo "   Please start the VM first: gcloud compute instances start airflow-vm --zone=asia-east1-b"
    exit 1
fi

echo "✅ VM is running, proceeding with fixes..."
echo ""

# Create the fix script to run on the VM
cat > /tmp/vm_fix_script.sh << 'EOF'
#!/bin/bash
set -e

echo "=== Creating airflow-container user ==="
AIRFLOW_UID=50000

# Create airflow-container user with UID 50000 if it doesn't exist
if ! getent passwd $AIRFLOW_UID > /dev/null; then
    echo "Creating airflow-container user with UID $AIRFLOW_UID..."
    sudo useradd --system --uid $AIRFLOW_UID --home-dir /opt/airflow --no-create-home --shell /bin/false --gid root airflow-container
    echo "✅ Created airflow-container user"
else
    echo "✅ User with UID $AIRFLOW_UID already exists"
fi

# Add airflow-container user to docker group
if getent passwd airflow-container > /dev/null; then
    sudo usermod -aG docker airflow-container
    echo "✅ Added airflow-container user to docker group"
fi

echo ""
echo "=== Updating GCS sync service ==="

# Stop the current GCS sync service
sudo systemctl stop gcs-sync.service

# Update the GCS sync service to run as airflow-container user
sudo tee /etc/systemd/system/gcs-sync.service > /dev/null << 'EOL'
[Unit]
Description=GCS DAGs Sync Service
After=network.target

[Service]
Type=simple
User=airflow-container
Group=root
ExecStart=/usr/bin/gsutil -m rsync -r gs://open-data-v2-cicd-airflow-storage/docker/dags/ /opt/airflow/dags/
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOL

# Reload systemd and restart the service
sudo systemctl daemon-reload
sudo systemctl enable gcs-sync.service
sudo systemctl start gcs-sync.service

echo "✅ Updated and restarted GCS sync service"
echo ""

echo "=== Checking service status ==="
sudo systemctl status gcs-sync.service --no-pager -l

echo ""
echo "=== Verifying DAG sync ==="
sleep 5  # Wait a moment for sync to happen
echo "DAGs in GCS:"
gsutil ls gs://open-data-v2-cicd-airflow-storage/docker/dags/
echo ""
echo "DAGs on VM:"
ls -la /opt/airflow/dags/

echo ""
echo "=== Restarting Airflow scheduler to pick up changes ==="
cd /opt/airflow
sudo docker-compose restart airflow-scheduler

echo ""
echo "=== Fixing gsutil permissions ==="
# Fix gsutil directory permissions for airflow-container user
sudo chown -R airflow-container:root /opt/airflow/.gsutil
echo "✅ Fixed gsutil directory permissions"

echo ""
echo "✅ Fix completed!"
EOF

# Copy and execute the fix script on the VM
echo "1️⃣ Copying fix script to VM..."
gcloud compute scp /tmp/vm_fix_script.sh airflow-vm:/tmp/vm_fix_script.sh --zone=asia-east1-b

echo ""
echo "2️⃣ Executing fix script on VM..."
gcloud compute ssh airflow-vm --zone=asia-east1-b --command="chmod +x /tmp/vm_fix_script.sh && /tmp/vm_fix_script.sh"

echo ""
echo "3️⃣ Cleaning up..."
rm -f /tmp/vm_fix_script.sh
gcloud compute ssh airflow-vm --zone=asia-east1-b --command="rm -f /tmp/vm_fix_script.sh"

echo ""
echo "🎉 SUCCESS: Airflow permissions have been fixed!"
echo ""
echo "📋 What was fixed:"
echo "   • Created airflow-container user with UID 50000"
echo "   • Updated GCS sync service to run as airflow-container user"
echo "   • Restarted GCS sync service"
echo "   • Restarted Airflow scheduler to pick up DAG changes"
echo "   • Fixed gsutil directory permissions"
echo ""
echo "🔍 To verify the fix:"
echo "   • Check GCS sync service: gcloud compute ssh airflow-vm --zone=asia-east1-b --command='sudo systemctl status gcs-sync.service'"
echo "   • Check DAGs: gcloud compute ssh airflow-vm --zone=asia-east1-b --command='ls -la /opt/airflow/dags/'"
echo "   • Access Airflow UI: http://$(gcloud compute instances describe airflow-vm --zone=asia-east1-b --format='get(networkInterfaces[0].accessConfigs[0].natIP)'):8081" 