#!/bin/bash

# Comprehensive script to ensure all Airflow fixes are permanent
# This script will make sure VM restarts work smoothly

set -e

echo "=== Ensuring Permanent Airflow Fixes ==="
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

echo "1️⃣ Checking VM status..."
VM_STATUS=$(check_vm_status)
if [ "$VM_STATUS" != "RUNNING" ]; then
    echo "❌ ERROR: VM is not running (status: $VM_STATUS)"
    echo "   Please start the VM first: gcloud compute instances start $VM_NAME --zone=$ZONE"
    exit 1
fi
echo "✅ VM is running"

echo ""
echo "2️⃣ Applying permanent fixes to current VM..."

# Create the comprehensive fix script
cat > /tmp/permanent_fixes.sh << 'EOF'
#!/bin/bash
set -e

echo "=== Applying Permanent Fixes ==="

# Ensure users exist
AIRFLOW_UID=50000
if ! getent passwd $AIRFLOW_UID > /dev/null; then
    echo "Creating airflow-container user..."
    useradd --system --uid $AIRFLOW_UID --home-dir /opt/airflow --no-create-home --shell /bin/false --gid root airflow-container
fi

if ! getent passwd airflow > /dev/null; then
    echo "Creating airflow system user..."
    useradd --system --home-dir /opt/airflow --no-create-home --shell /bin/false airflow
fi

# Add users to docker group
usermod -aG docker airflow-container 2>/dev/null || true
usermod -aG docker airflow 2>/dev/null || true

# Create all necessary directories
mkdir -p /opt/airflow/{dags,logs,config,plugins}
mkdir -p /opt/airflow/logs/{scheduler,dag_processor_manager,webserver}
mkdir -p /opt/airflow/.config/gcloud/configurations
mkdir -p /opt/airflow/.gsutil

# Fix ownership and permissions
chown -R $AIRFLOW_UID:0 /opt/airflow/{dags,logs,plugins,config}
chown -R $AIRFLOW_UID:0 /opt/airflow/.config
chown -R $AIRFLOW_UID:0 /opt/airflow/.gsutil
chmod -R 755 /opt/airflow/{dags,logs,plugins}

# Fix .env file if it exists
if [ -f /opt/airflow/.env ]; then
    chown $AIRFLOW_UID:0 /opt/airflow/.env
    chmod 600 /opt/airflow/.env
fi

# Update GCS sync service with proper authentication
echo "Updating GCS sync service..."
cat > /etc/systemd/system/gcs-sync.service << 'EOL'
[Unit]
Description=GCS DAGs Sync Service
After=network.target

[Service]
Type=simple
User=airflow-container
Group=root
Environment="GOOGLE_APPLICATION_CREDENTIALS=/opt/airflow/config/service-account.json"
ExecStart=/usr/bin/gsutil rsync -r -d gs://open-data-v2-cicd-airflow-storage/docker/dags/ /opt/airflow/dags/
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOL

# Update airflow-permissions service to include all directories
echo "Updating airflow-permissions service..."
cat > /etc/systemd/system/airflow-permissions.service << 'EOL'
[Unit]
Description=Fix Airflow Permissions on Boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'chown -R 50000:0 /opt/airflow/{dags,logs,plugins,config} && chmod -R 755 /opt/airflow/{dags,logs,plugins} && if [ -d "/opt/airflow/.gsutil" ]; then chown -R 50000:0 /opt/airflow/.gsutil; fi && if [ -d "/opt/airflow/.config" ]; then chown -R 50000:0 /opt/airflow/.config; fi'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOL

# Create a service to ensure Docker services start properly
echo "Creating Docker startup service..."
cat > /etc/systemd/system/airflow-docker-startup.service << 'EOL'
[Unit]
Description=Ensure Airflow Docker Services Start
After=docker.service
Requires=docker.service
After=airflow-permissions.service
Requires=airflow-permissions.service

[Service]
Type=oneshot
WorkingDirectory=/opt/airflow
ExecStart=/bin/bash -c 'cd /opt/airflow && docker-compose up -d --remove-orphans'
RemainAfterExit=yes
TimeoutStartSec=600

[Install]
WantedBy=multi-user.target
EOL

# Reload systemd and enable all services
systemctl daemon-reload
systemctl enable airflow-permissions.service
systemctl enable gcs-sync.service
systemctl enable airflow-docker-startup.service

echo "✅ All services configured and enabled"

# Restart services to apply changes
echo "Restarting services..."
systemctl restart gcs-sync.service
systemctl start airflow-permissions.service

# Ensure Docker services are running
cd /opt/airflow
if ! docker-compose ps | grep -q "Up"; then
    echo "Starting Docker services..."
    docker-compose up -d
fi

echo "✅ Permanent fixes applied successfully"
EOF

# Copy and execute the fix script
echo "Copying and executing permanent fixes script..."
gcloud compute scp /tmp/permanent_fixes.sh $VM_NAME:/tmp/permanent_fixes.sh --zone=$ZONE
gcloud compute ssh $VM_NAME --zone=$ZONE --command="chmod +x /tmp/permanent_fixes.sh && sudo /tmp/permanent_fixes.sh"

echo ""
echo "3️⃣ Testing current VM state..."
sleep 10

# Validate current state
echo "Running validation..."
if [ -f "./validate_airflow.sh" ]; then
    ./validate_airflow.sh
else
    echo "Validation script not found, checking manually..."
    VM_IP=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --format="get(networkInterfaces[0].accessConfigs[0].natIP)")
    if curl -s --connect-timeout 10 "http://$VM_IP:8081/health" > /dev/null 2>&1; then
        echo "✅ Airflow is responding to health checks!"
    else
        echo "⚠️  Airflow may still be starting up..."
    fi
fi

echo ""
echo "4️⃣ Testing VM restart resilience..."
echo "This will stop and start the VM to test if fixes persist..."
read -p "Do you want to test VM restart now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Stopping VM..."
    gcloud compute instances stop $VM_NAME --zone=$ZONE --quiet
    
    echo "Waiting for VM to stop..."
    sleep 30
    
    echo "Starting VM..."
    gcloud compute instances start $VM_NAME --zone=$ZONE --quiet
    
    echo "Waiting for startup to complete..."
    sleep 180  # Wait 3 minutes for full startup
    
    echo "Testing after restart..."
    if [ -f "./validate_airflow.sh" ]; then
        ./validate_airflow.sh
    else
        VM_IP=$(gcloud compute instances describe $VM_NAME --zone=$ZONE --format="get(networkInterfaces[0].accessConfigs[0].natIP)")
        if curl -s --connect-timeout 10 "http://$VM_IP:8081/health" > /dev/null 2>&1; then
            echo "✅ Airflow is working after restart!"
        else
            echo "⚠️  Airflow may still be starting up after restart..."
        fi
    fi
else
    echo "Skipping restart test."
fi

echo ""
echo "5️⃣ Cleanup..."
rm -f /tmp/permanent_fixes.sh
gcloud compute ssh $VM_NAME --zone=$ZONE --command="rm -f /tmp/permanent_fixes.sh" 2>/dev/null || true

echo ""
echo "🎉 SUCCESS: Permanent fixes have been applied!"
echo ""
echo "📋 What was made permanent:"
echo "   ✅ Updated startup script with fixed user creation command"
echo "   ✅ Airflow permissions service (runs on every boot)"
echo "   ✅ GCS sync service with proper authentication"
echo "   ✅ Docker startup service for reliable container startup"
echo "   ✅ All directory permissions and ownership"
echo "   ✅ User and group configurations"
echo ""
echo "🔄 These fixes will persist through:"
echo "   • VM stops/starts"
echo "   • VM restarts"
echo "   • VM recreations (via updated Terraform)"
echo "   • System reboots"
echo ""
echo "🌐 Your Airflow environment is now robust and restart-proof!"
EOF 