#!/bin/bash

# Airflow Management Script
# Comprehensive tool for managing Airflow VM operations

set -e

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

# Function to print colored output
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

# Function to validate Airflow
validate_airflow() {
    echo "=== Airflow Validation ==="
    echo "Timestamp: $(date)"
    echo ""

    VM_IP=$(get_vm_ip)
    if [ -z "$VM_IP" ]; then
        print_error "Could not get VM IP. Is the VM running?"
        return 1
    fi

    print_info "VM IP: $VM_IP"
    echo ""

    # Test VM connectivity
    echo "1️⃣ Testing VM connectivity..."
    if ping -c 3 "$VM_IP" > /dev/null 2>&1; then
        print_status "VM is reachable"
    else
        print_error "VM is not reachable"
        return 1
    fi

    # Test Airflow port
    echo ""
    echo "2️⃣ Testing Airflow port 8081..."
    if curl -s --connect-timeout 10 "http://$VM_IP:8081/health" > /dev/null; then
        print_status "Port 8081 is accessible"
    else
        print_error "Port 8081 is not accessible"
        return 1
    fi

    # Test health endpoint
    echo ""
    echo "3️⃣ Testing Airflow health endpoint..."
    HEALTH_RESPONSE=$(curl -s --connect-timeout 10 "http://$VM_IP:8081/health" 2>/dev/null || echo "")
    if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
        print_status "Airflow health check passed"
    else
        print_error "Airflow health check failed"
        return 1
    fi

    # Test web UI
    echo ""
    echo "4️⃣ Testing Airflow web UI..."
    UI_RESPONSE=$(curl -s --connect-timeout 10 -w "%{http_code}" "http://$VM_IP:8081/" -o /dev/null 2>/dev/null || echo "000")
    if [ "$UI_RESPONSE" = "302" ] || [ "$UI_RESPONSE" = "200" ]; then
        print_status "Web UI is accessible (HTTP $UI_RESPONSE)"
    else
        print_error "Web UI is not accessible (HTTP $UI_RESPONSE)"
        return 1
    fi

    # Check services
    echo ""
    echo "5️⃣ Checking services on VM..."
    SERVICE_STATUS=$(gcloud compute ssh $VM_NAME --zone=$ZONE --command="cd /opt/airflow && sudo docker-compose ps --format table" 2>/dev/null || echo "")
    if echo "$SERVICE_STATUS" | grep -q "Up"; then
        print_status "Docker services are running"
        RUNNING_SERVICES=$(echo "$SERVICE_STATUS" | grep "Up" | wc -l)
        print_info "Running services: $RUNNING_SERVICES"
    else
        print_error "Docker services are not running properly"
        return 1
    fi

    echo ""
    echo "=== Validation Summary ==="
    print_status "SUCCESS: Airflow is running and accessible!"
    echo ""
    echo "🌐 Access Airflow UI: http://$VM_IP:8081"
    echo "👤 Username: admin"
    echo "🔑 Password: admin"
    
    return 0
}

# Function to restart VM
restart_vm() {
    echo "=== Airflow VM Restart ==="
    echo "Timestamp: $(date)"
    echo ""

    # Check current status
    echo "1️⃣ Checking current VM status..."
    current_status=$(check_vm_status)
    echo "Current VM status: $current_status"

    if [ "$current_status" = "NOT_FOUND" ]; then
        print_error "VM not found! Please check if it exists."
        return 1
    fi

    # Stop VM if running
    echo ""
    echo "2️⃣ Stopping VM..."
    if [ "$current_status" = "RUNNING" ]; then
        gcloud compute instances stop $VM_NAME --zone=$ZONE --quiet
        print_info "VM stop command sent"
        
        # Wait for VM to stop
        echo "Waiting for VM to stop..."
        timeout=120
        while [ $timeout -gt 0 ]; do
            status=$(check_vm_status)
            if [ "$status" = "TERMINATED" ]; then
                print_status "VM is now stopped"
                break
            fi
            echo "VM status: $status, waiting..."
            sleep 5
            timeout=$((timeout - 5))
        done
    else
        print_info "VM is already stopped (status: $current_status)"
    fi

    # Start VM
    echo ""
    echo "3️⃣ Starting VM..."
    gcloud compute instances start $VM_NAME --zone=$ZONE --quiet
    print_info "VM start command sent"

    # Wait for VM to be running
    echo "Waiting for VM to be running..."
    timeout=300
    while [ $timeout -gt 0 ]; do
        status=$(check_vm_status)
        if [ "$status" = "RUNNING" ]; then
            print_status "VM is now RUNNING"
            break
        fi
        echo "VM status: $status, waiting... $(($timeout / 10)) checks remaining"
        sleep 10
        timeout=$((timeout - 10))
    done

    if [ $timeout -eq 0 ]; then
        print_error "VM failed to reach RUNNING state within timeout"
        return 1
    fi

    # Get VM IP
    echo ""
    echo "4️⃣ Getting VM IP..."
    vm_ip=$(get_vm_ip)
    if [ -z "$vm_ip" ]; then
        print_error "Failed to get VM IP"
        return 1
    fi
    print_info "VM IP: $vm_ip"

    # Wait for startup script to complete
    echo ""
    echo "5️⃣ Waiting for startup script to complete..."
    print_info "This may take several minutes as Docker containers are started..."
    sleep 120  # Wait 2 minutes for startup

    # Validate Airflow
    echo ""
    echo "6️⃣ Validating Airflow..."
    if validate_airflow; then
        print_status "SUCCESS: Airflow VM restart completed successfully!"
    else
        print_warning "Airflow restart completed but validation failed"
        print_info "Services may still be initializing. Try validation again in a few minutes."
    fi
}

# Function to apply permanent fixes
apply_permanent_fixes() {
    echo "=== Applying Permanent Fixes ==="
    echo "Timestamp: $(date)"
    echo ""

    # Check VM status
    VM_STATUS=$(check_vm_status)
    if [ "$VM_STATUS" != "RUNNING" ]; then
        print_error "VM is not running (status: $VM_STATUS)"
        print_info "Please start the VM first: gcloud compute instances start $VM_NAME --zone=$ZONE"
        return 1
    fi
    print_status "VM is running"

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
ExecStart=/usr/bin/gsutil -m rsync -r -d gs://open-data-v2-cicd-airflow-storage/docker/dags/ /opt/airflow/dags/
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOL

# Update airflow-permissions service
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

# Reload systemd and enable services
systemctl daemon-reload
systemctl enable airflow-permissions.service
systemctl enable gcs-sync.service

echo "✅ All services configured and enabled"

# Restart services to apply changes
echo "Restarting services..."
systemctl restart gcs-sync.service
systemctl start airflow-permissions.service

# Ensure Docker services are running
cd /opt/airflow
if ! docker-compose ps | grep -q "Up.*Up.*Up"; then
    echo "Starting Docker services..."
    docker-compose up -d
fi

echo "✅ Permanent fixes applied successfully"
EOF

    # Copy and execute the fix script
    echo "Copying and executing permanent fixes script..."
    gcloud compute scp /tmp/permanent_fixes.sh $VM_NAME:/tmp/permanent_fixes.sh --zone=$ZONE
    gcloud compute ssh $VM_NAME --zone=$ZONE --command="chmod +x /tmp/permanent_fixes.sh && sudo /tmp/permanent_fixes.sh"

    # Cleanup
    rm -f /tmp/permanent_fixes.sh
    gcloud compute ssh $VM_NAME --zone=$ZONE --command="rm -f /tmp/permanent_fixes.sh" 2>/dev/null || true

    print_status "Permanent fixes applied successfully!"
}

# Emergency fix function for severe restart issues
emergency_fix() {
    echo "=== Emergency Airflow VM Fix ==="
    echo "Timestamp: $(date)"
    echo ""

    # Check VM status
    VM_STATUS=$(check_vm_status)
    if [ "$VM_STATUS" != "RUNNING" ]; then
        print_error "VM is not running (status: $VM_STATUS)"
        print_info "Please start the VM first: gcloud compute instances start $VM_NAME --zone=$ZONE"
        return 1
    fi

    print_status "VM is running, applying emergency fixes..."

    # Create comprehensive emergency fix script
    cat > /tmp/emergency_vm_fix.sh << 'EOF'
#!/bin/bash
set -e

echo "=== Emergency VM Fix Starting ==="

# 1. Fix dpkg issues
echo "1️⃣ Fixing dpkg issues..."
export DEBIAN_FRONTEND=noninteractive
dpkg --configure -a || true
apt-get -f install -y || true

# 2. Complete any interrupted package operations
echo "2️⃣ Updating packages..."
apt-get update -y
apt-get upgrade -y

# 3. Install Docker if not present
echo "3️⃣ Ensuring Docker is installed..."
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    apt-get install -y apt-transport-https ca-certificates curl software-properties-common
    curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add -
    add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_release -cs) stable"
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io
    systemctl enable docker
    systemctl start docker
else
    echo "Docker already installed"
    systemctl restart docker
fi

# 4. Install Docker Compose if not present
echo "4️⃣ Ensuring Docker Compose is installed..."
if ! command -v docker-compose &> /dev/null; then
    echo "Installing Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
else
    echo "Docker Compose already installed"
fi

# 5. Install Python packages
echo "5️⃣ Installing Python packages..."
pip3 install --upgrade cryptography

# 6. Ensure users exist
echo "6️⃣ Setting up users..."
AIRFLOW_UID=50000
if ! getent passwd $AIRFLOW_UID > /dev/null; then
    useradd --system --uid $AIRFLOW_UID --home-dir /opt/airflow --no-create-home --shell /bin/false --gid root airflow-container
fi
if ! getent passwd airflow > /dev/null; then
    useradd --system --home-dir /opt/airflow --no-create-home --shell /bin/false airflow
fi

# Add users to docker group
usermod -aG docker airflow-container 2>/dev/null || true
usermod -aG docker airflow 2>/dev/null || true

# 7. Set up directories
echo "7️⃣ Setting up directories..."
mkdir -p /opt/airflow/{dags,logs,config,plugins}
mkdir -p /opt/airflow/logs/{scheduler,dag_processor_manager,webserver}
mkdir -p /opt/airflow/.config/gcloud/configurations
mkdir -p /opt/airflow/.gsutil

# 8. Get configurations from GCS if needed
echo "8️⃣ Getting configurations from GCS..."
cd /opt/airflow
if [ ! -f "docker-compose.yml" ]; then
    echo "Downloading configurations from GCS..."
    gsutil -m cp -r gs://open-data-v2-cicd-airflow-storage/docker/* . 2>/dev/null || echo "Could not download from GCS, continuing..."
fi

# 9. Create service account key if missing
echo "9️⃣ Setting up service account..."
mkdir -p /opt/airflow/config
if [ ! -f "/opt/airflow/config/service-account.json" ]; then
    gcloud secrets versions access latest --secret="airflow-service-account-key" > /opt/airflow/config/service-account.json 2>/dev/null || echo "Could not fetch service account key"
fi

# 10. Create environment file if missing
echo "🔟 Creating environment file..."
if [ ! -f ".env" ]; then
    FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    AIRFLOW_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(16))")
    
    cat > .env << EOL
AIRFLOW_UID=50000
AIRFLOW_GID=0
AIRFLOW_FERNET_KEY=$FERNET_KEY
AIRFLOW_SECRET_KEY=$AIRFLOW_SECRET_KEY
AIRFLOW_GCS_BUCKET=open-data-v2-cicd-airflow-storage
GOOGLE_CLOUD_PROJECT=open-data-v2-cicd
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD=admin
AIRFLOW_ADMIN_FIRSTNAME=Airflow
AIRFLOW_ADMIN_LASTNAME=Admin
AIRFLOW_ADMIN_EMAIL=admin@example.com
AIRFLOW_DB_CONNECTION=postgresql+psycopg2://airflow:airflow@postgres/airflow
EOL
fi

# 11. Fix all permissions
echo "1️⃣1️⃣ Fixing permissions..."
chown -R $AIRFLOW_UID:0 /opt/airflow/{dags,logs,plugins,config}
chown -R $AIRFLOW_UID:0 /opt/airflow/.config
chown -R $AIRFLOW_UID:0 /opt/airflow/.gsutil
chmod -R 755 /opt/airflow/{dags,logs,plugins}
chown $AIRFLOW_UID:0 .env
chmod 600 .env

# 12. Update systemd services
echo "1️⃣2️⃣ Updating systemd services..."

# GCS sync service
cat > /etc/systemd/system/gcs-sync.service << 'EOL'
[Unit]
Description=GCS DAGs Sync Service
After=network.target

[Service]
Type=simple
User=airflow-container
Group=root
Environment="GOOGLE_APPLICATION_CREDENTIALS=/opt/airflow/config/service-account.json"
ExecStart=/usr/bin/gsutil -m rsync -r -d gs://open-data-v2-cicd-airflow-storage/docker/dags/ /opt/airflow/dags/
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOL

# Airflow permissions service
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

# Airflow startup service
cat > /etc/systemd/system/airflow-startup.service << 'EOL'
[Unit]
Description=Start Airflow Services
After=docker.service airflow-permissions.service
Requires=docker.service
Wants=airflow-permissions.service

[Service]
Type=oneshot
WorkingDirectory=/opt/airflow
ExecStartPre=/bin/bash -c 'while ! docker info > /dev/null 2>&1; do echo "Waiting for Docker..."; sleep 2; done'
ExecStart=/bin/bash -c 'cd /opt/airflow && docker-compose up -d'
RemainAfterExit=yes
TimeoutStartSec=600

[Install]
WantedBy=multi-user.target
EOL

# 13. Enable and start services
echo "1️⃣3️⃣ Enabling services..."
systemctl daemon-reload
systemctl enable airflow-permissions.service
systemctl enable gcs-sync.service
systemctl enable airflow-startup.service

# Start permission service
systemctl start airflow-permissions.service

# 14. Start Docker services
echo "1️⃣4️⃣ Starting Docker services..."
cd /opt/airflow

# Clean up any existing containers
docker-compose down -v 2>/dev/null || true

# Start services step by step
echo "Starting Postgres..."
docker-compose up -d postgres

# Wait for Postgres
echo "Waiting for Postgres to be healthy..."
timeout=120
while [ $timeout -gt 0 ]; do
    if docker-compose exec -T postgres pg_isready -U airflow 2>/dev/null; then
        echo "Postgres is ready!"
        break
    fi
    echo "Waiting for Postgres... $timeout seconds remaining"
    sleep 5
    timeout=$((timeout - 5))
done

# Initialize database
echo "Initializing Airflow database..."
docker-compose run --rm airflow-init 2>/dev/null || {
    echo "Airflow init failed, trying manual setup..."
    docker-compose run --rm airflow-init airflow db migrate 2>/dev/null || true
    docker-compose run --rm airflow-init airflow users create --username admin --password admin --firstname Airflow --lastname Admin --role Admin --email admin@example.com 2>/dev/null || true
}

# Start remaining services
echo "Starting Airflow services..."
docker-compose up -d airflow-webserver airflow-scheduler

echo "✅ Emergency fix completed!"
echo "Services should be starting up now..."

# Show status
echo ""
echo "Service status:"
docker-compose ps
EOF

    echo "Copying and executing emergency fix script..."
    gcloud compute scp /tmp/emergency_vm_fix.sh $VM_NAME:/tmp/emergency_vm_fix.sh --zone=$ZONE
    gcloud compute ssh $VM_NAME --zone=$ZONE --command="chmod +x /tmp/emergency_vm_fix.sh && sudo /tmp/emergency_vm_fix.sh"

    echo ""
    print_info "Waiting for services to stabilize..."
    sleep 60

    echo ""
    echo "Validating fix..."
    VM_IP=$(get_vm_ip)
    print_info "VM IP: $VM_IP"

    # Test health endpoint
    if curl -s --connect-timeout 10 "http://$VM_IP:8081/health" > /dev/null 2>&1; then
        print_status "SUCCESS: Airflow is now accessible!"
        echo ""
        echo "🌐 Access Airflow UI: http://$VM_IP:8081"
        echo "👤 Username: admin"
        echo "🔑 Password: admin"
    else
        print_info "Airflow may still be starting up. Check status with:"
        echo "   $0 status"
    fi

    # Cleanup
    rm -f /tmp/emergency_vm_fix.sh
    gcloud compute ssh $VM_NAME --zone=$ZONE --command="rm -f /tmp/emergency_vm_fix.sh" 2>/dev/null || true

    print_status "Emergency fix completed!"
}

# Function to upload DAGs
upload_dags() {
    echo "=== Uploading DAGs to GCS ==="
    
    SOURCE_DIR="../terraform/airflow/docker/dags"
    DESTINATION="gs://${BUCKET_NAME}/docker/dags/"

    if [ ! -d "$SOURCE_DIR" ]; then
        print_error "Source directory $SOURCE_DIR does not exist"
        return 1
    fi

    print_info "Syncing DAGs from $SOURCE_DIR to $DESTINATION"
    gsutil -m rsync -r -d "$SOURCE_DIR" "$DESTINATION"
    
    print_status "Successfully synced Airflow DAGs to $DESTINATION"
}

# Function to show help
show_help() {
    echo "Airflow Management Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  validate       - Validate Airflow is running and accessible"
    echo "  restart        - Restart the Airflow VM"
    echo "  fix            - Apply permanent fixes to prevent restart issues"
    echo "  emergency-fix  - Apply comprehensive emergency fixes for severe issues"
    echo "  upload         - Upload DAGs to GCS bucket"
    echo "  status         - Show current VM and service status"
    echo "  help           - Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 validate"
    echo "  $0 restart"
    echo "  $0 fix"
    echo "  $0 emergency-fix    # Use when services fail to start after restart"
    echo ""
}

# Function to show status
show_status() {
    echo "=== Airflow Status ==="
    echo "Timestamp: $(date)"
    echo ""
    
    VM_STATUS=$(check_vm_status)
    echo "VM Status: $VM_STATUS"
    
    if [ "$VM_STATUS" = "RUNNING" ]; then
        VM_IP=$(get_vm_ip)
        echo "VM IP: $VM_IP"
        
        echo ""
        echo "Docker Services:"
        gcloud compute ssh $VM_NAME --zone=$ZONE --command="cd /opt/airflow && sudo docker-compose ps" 2>/dev/null || echo "Could not retrieve service status"
        
        echo ""
        echo "System Services:"
        gcloud compute ssh $VM_NAME --zone=$ZONE --command="sudo systemctl status airflow-permissions.service gcs-sync.service --no-pager -l" 2>/dev/null || echo "Could not retrieve system service status"
    fi
}

# Main script logic
case "${1:-help}" in
    validate)
        validate_airflow
        ;;
    restart)
        restart_vm
        ;;
    fix)
        apply_permanent_fixes
        echo ""
        print_info "Testing fixes..."
        sleep 10
        validate_airflow
        ;;
    emergency-fix)
        emergency_fix
        ;;
    upload)
        upload_dags
        ;;
    status)
        show_status
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac 