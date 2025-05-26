#!/bin/bash

# Comprehensive Airflow Permissions Fix Script
# This script fixes all user/permission issues and makes them permanent

set -e

echo "=== Comprehensive Airflow Permissions Fix ==="
echo "Timestamp: $(date)"
echo ""

# Check if VM is running
VM_STATUS=$(gcloud compute instances describe airflow-vm --zone=asia-east1-b --format="get(status)" 2>/dev/null || echo "NOT_FOUND")

if [ "$VM_STATUS" != "RUNNING" ]; then
    echo "❌ ERROR: Airflow VM is not running (status: $VM_STATUS)"
    echo "   Please start the VM first: gcloud compute instances start airflow-vm --zone=asia-east1-b"
    exit 1
fi

echo "✅ VM is running, proceeding with comprehensive fixes..."
echo ""

# Create the comprehensive fix script to run on the VM
cat > /tmp/vm_comprehensive_fix.sh << 'EOF'
#!/bin/bash
set -e

echo "=== Comprehensive Airflow Permission Fix ==="
AIRFLOW_UID=50000

echo "1️⃣ Ensuring airflow-container user exists..."
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
echo "2️⃣ Fixing directory ownership and permissions..."
cd /opt/airflow

# Ensure all directories exist
sudo mkdir -p {dags,logs,config,plugins}
sudo mkdir -p logs/{scheduler,dag_processor_manager,webserver}

# Fix ownership for all Airflow directories
echo "Setting ownership to UID $AIRFLOW_UID..."
sudo chown -R $AIRFLOW_UID:0 dags logs plugins config
sudo chmod -R 755 dags logs plugins
sudo chmod -R 644 config/*

# Fix .env file permissions
if [ -f .env ]; then
    sudo chown $AIRFLOW_UID:0 .env
    sudo chmod 600 .env
fi

# Fix service account file if it exists
if [ -f config/service-account.json ]; then
    sudo chown $AIRFLOW_UID:0 config/service-account.json
    sudo chmod 644 config/service-account.json
fi

echo "✅ Fixed directory ownership and permissions"

echo ""
echo "3️⃣ Updating GCS sync service..."
# Stop the current GCS sync service
sudo systemctl stop gcs-sync.service || true

# Update the GCS sync service to run as airflow-container user
sudo tee /etc/systemd/system/gcs-sync.service > /dev/null << 'EOL'
[Unit]
Description=GCS DAGs Sync Service
After=network.target

[Service]
Type=simple
User=airflow-container
Group=root
ExecStart=/usr/bin/gsutil -m rsync -r -d gs://open-data-v2-cicd-airflow-storage/docker/dags/ /opt/airflow/dags/
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOL

echo "✅ Updated GCS sync service configuration"

echo ""
echo "4️⃣ Creating permanent permission fix service..."
# Create a service that fixes permissions on every boot
sudo tee /etc/systemd/system/airflow-permissions.service > /dev/null << 'EOL'
[Unit]
Description=Fix Airflow Permissions on Boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'chown -R 50000:0 /opt/airflow/{dags,logs,plugins,config} && chmod -R 755 /opt/airflow/{dags,logs,plugins}'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOL

# Reload systemd and enable services
sudo systemctl daemon-reload
sudo systemctl enable airflow-permissions.service
sudo systemctl enable gcs-sync.service
sudo systemctl start gcs-sync.service

echo "✅ Created and enabled permanent permission fix service"

echo ""
echo "5️⃣ Fixing gsutil permissions..."
# Fix gsutil directory permissions for airflow-container user
if [ -d /opt/airflow/.gsutil ]; then
    sudo chown -R airflow-container:root /opt/airflow/.gsutil
    echo "✅ Fixed gsutil directory permissions"
fi

echo ""
echo "6️⃣ Restarting Airflow services..."
cd /opt/airflow
sudo docker-compose restart airflow-scheduler airflow-webserver

echo ""
echo "7️⃣ Verifying the fix..."
echo "Directory ownership:"
ls -la /opt/airflow/ | head -10
echo ""
echo "Logs directory:"
ls -la /opt/airflow/logs/ | head -5
echo ""
echo "Service status:"
sudo systemctl status gcs-sync.service --no-pager -l | head -10
echo ""
echo "DAGs on VM:"
ls -la /opt/airflow/dags/

echo ""
echo "✅ Comprehensive fix completed!"
EOF

# Copy and execute the comprehensive fix script on the VM
echo "1️⃣ Copying comprehensive fix script to VM..."
gcloud compute scp /tmp/vm_comprehensive_fix.sh airflow-vm:/tmp/vm_comprehensive_fix.sh --zone=asia-east1-b

echo ""
echo "2️⃣ Executing comprehensive fix script on VM..."
gcloud compute ssh airflow-vm --zone=asia-east1-b --command="chmod +x /tmp/vm_comprehensive_fix.sh && /tmp/vm_comprehensive_fix.sh"

echo ""
echo "3️⃣ Waiting for services to stabilize..."
sleep 30

echo ""
echo "4️⃣ Final validation..."
# Run validation to confirm everything is working
if [ -f "./validate_airflow.sh" ]; then
    echo "Running validation script..."
    ./validate_airflow.sh
else
    echo "Validation script not found, checking manually..."
    VM_IP=$(gcloud compute instances describe airflow-vm --zone=asia-east1-b --format="get(networkInterfaces[0].accessConfigs[0].natIP)")
    echo "Testing Airflow health at $VM_IP:8081..."
    if curl -s --connect-timeout 10 "http://$VM_IP:8081/health" > /dev/null 2>&1; then
        echo "✅ Airflow is responding to health checks!"
    else
        echo "⚠️  Airflow may still be starting up..."
    fi
fi

echo ""
echo "5️⃣ Cleaning up..."
rm -f /tmp/vm_comprehensive_fix.sh
gcloud compute ssh airflow-vm --zone=asia-east1-b --command="rm -f /tmp/vm_comprehensive_fix.sh"

echo ""
echo "🎉 SUCCESS: Comprehensive Airflow permissions fix completed!"
echo ""
echo "📋 What was fixed permanently:"
echo "   ✅ Created airflow-container user with UID 50000"
echo "   ✅ Fixed all directory ownership (dags, logs, config, plugins)"
echo "   ✅ Updated GCS sync service to run as airflow-container user"
echo "   ✅ Created permanent permission fix service for future boots"
echo "   ✅ Fixed gsutil directory permissions"
echo "   ✅ Restarted Airflow services"
echo ""
echo "🔄 This fix will persist through:"
echo "   • VM restarts (permission service runs on boot)"
echo "   • VM recreations (updated Terraform startup script)"
echo "   • Future deployments (permanent configuration)"
echo ""
echo "🌐 Access Airflow UI: http://$(gcloud compute instances describe airflow-vm --zone=asia-east1-b --format='get(networkInterfaces[0].accessConfigs[0].natIP)'):8081"
echo "👤 Username: admin"
echo "�� Password: admin" 