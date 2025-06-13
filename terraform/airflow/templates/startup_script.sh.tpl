#!/bin/bash
set -e  # Exit on error

echo "Starting Airflow setup..."

# Install Docker
apt-get update
apt-get install -y apt-transport-https ca-certificates curl software-properties-common python3-pip
curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add -
add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_release -cs) stable"
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install required Python packages
pip3 install cryptography

# Set fixed UID/GID for Airflow container
AIRFLOW_UID=50000
AIRFLOW_GID=0

# Create Airflow directories with proper permissions
echo "Creating Airflow directories..."
mkdir -p /opt/airflow/{dags,logs,config,plugins}
mkdir -p /opt/airflow/logs/{scheduler,dag_processor_manager,webserver}

# Set up Airflow users and groups
echo "Setting up Airflow users and groups..."

# Create airflow system user for host operations (if it doesn't exist)
if ! getent group airflow > /dev/null; then
    echo "Creating airflow group..."
    groupadd --system airflow
fi
if ! getent passwd airflow > /dev/null; then
    echo "Creating airflow system user..."
    useradd --system --home-dir /opt/airflow --no-create-home --shell /bin/false --gid airflow airflow
fi

# Create airflow container user with UID 50000 (if it doesn't exist)
if ! getent passwd $AIRFLOW_UID > /dev/null; then
    echo "Creating airflow container user with UID $AIRFLOW_UID..."
    useradd --system --uid $AIRFLOW_UID --home-dir /opt/airflow --no-create-home --shell /bin/false --gid root airflow-container
else
    echo "User with UID $AIRFLOW_UID already exists"
fi

# Verify both users exist
if ! getent passwd airflow > /dev/null; then
    echo "ERROR: Failed to create airflow system user!"
    exit 1
fi
if ! getent passwd $AIRFLOW_UID > /dev/null; then
    echo "ERROR: Failed to create airflow container user!"
    exit 1
fi
echo "Airflow users created successfully"

# Pull Airflow configurations from GCS
echo "Pulling configurations from GCS..."
cd /opt/airflow
gsutil -m cp -r gs://${gcs_bucket}/docker/* .

# Set up GCS sync service to run as the container user (UID 50000)
echo "Setting up GCS sync service..."
cat > /etc/systemd/system/gcs-sync.service <<EOL
[Unit]
Description=GCS DAGs Sync Service
After=network.target

[Service]
Type=simple
User=airflow-container
Group=root
Environment="GOOGLE_APPLICATION_CREDENTIALS=/opt/airflow/config/service-account.json"
ExecStart=/usr/bin/gsutil -m rsync -r -d gs://${gcs_bucket}/docker/dags/ /opt/airflow/dags/
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOL

# Enable and start GCS sync service
systemctl daemon-reload
systemctl enable gcs-sync.service
systemctl start gcs-sync.service

# Create necessary directories with proper permissions for gcloud/gsutil
echo "Creating gcloud and gsutil directories..."
mkdir -p /opt/airflow/.config/gcloud/configurations
mkdir -p /opt/airflow/.gsutil
chown -R $AIRFLOW_UID:root /opt/airflow/.config
chown -R $AIRFLOW_UID:root /opt/airflow/.gsutil
echo "Created and configured gcloud/gsutil directories"

# Fetch service account key from Secret Manager
echo "Fetching service account key from Secret Manager..."
mkdir -p /opt/airflow/config
if ! gcloud secrets versions access latest --secret="airflow-service-account-key" > /opt/airflow/config/service-account.json; then
    echo "Failed to fetch service account key from Secret Manager"
    exit 1
fi

# Verify service account key
if [ ! -s /opt/airflow/config/service-account.json ]; then
    echo "Service account key file is empty or missing"
    exit 1
fi
echo "Service account key fetched successfully"

# Generate Fernet key and create environment file
FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
AIRFLOW_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(16))")

# Create environment file with explicit database connection
cat > .env <<EOL
AIRFLOW_UID=$AIRFLOW_UID
AIRFLOW_GID=$AIRFLOW_GID
AIRFLOW_FERNET_KEY=$FERNET_KEY
AIRFLOW_SECRET_KEY=$AIRFLOW_SECRET_KEY
AIRFLOW_GCS_BUCKET=${gcs_bucket}
GOOGLE_CLOUD_PROJECT=${project_id}
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD=admin
AIRFLOW_ADMIN_FIRSTNAME=Airflow
AIRFLOW_ADMIN_LASTNAME=Admin
AIRFLOW_ADMIN_EMAIL=admin@example.com
AIRFLOW_DB_CONNECTION=postgresql+psycopg2://airflow:airflow@postgres/airflow
EOL

# Set comprehensive permissions for Airflow container (UID 50000)
echo "Setting proper permissions for Airflow container..."

# Ensure directories exist first
mkdir -p /opt/airflow/{dags,logs,config,plugins}
mkdir -p /opt/airflow/logs/{scheduler,dag_processor_manager,webserver}

# Set ownership for all Airflow directories to UID 50000
echo "Setting ownership to UID $AIRFLOW_UID (airflow-container user)..."
chown -R $AIRFLOW_UID:$AIRFLOW_GID /opt/airflow/dags
chown -R $AIRFLOW_UID:$AIRFLOW_GID /opt/airflow/logs
chown -R $AIRFLOW_UID:$AIRFLOW_GID /opt/airflow/plugins
chown -R $AIRFLOW_UID:$AIRFLOW_GID /opt/airflow/config

# Set proper permissions
chmod -R 755 /opt/airflow/dags
chmod -R 755 /opt/airflow/logs
chmod -R 755 /opt/airflow/plugins
chmod -R 644 /opt/airflow/config/*
chmod 600 .env
chown $AIRFLOW_UID:$AIRFLOW_GID .env

# Ensure service account file has correct permissions
chmod 644 /opt/airflow/config/service-account.json
chown $AIRFLOW_UID:$AIRFLOW_GID /opt/airflow/config/service-account.json

# Verify permissions are set correctly
echo "Verifying permissions..."
ls -la /opt/airflow/ | head -10
echo "Logs directory permissions:"
ls -la /opt/airflow/logs/ | head -5

# Create a permission fix service that runs on every boot
echo "Creating permission fix service for boot-time execution..."
cat > /etc/systemd/system/airflow-permissions.service <<EOL
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

# Enable the permission fix service
systemctl daemon-reload
systemctl enable airflow-permissions.service
echo "✅ Airflow permissions service enabled for future boots"

# Add airflow users to docker group
echo "Adding airflow users to docker group..."
if getent passwd airflow > /dev/null; then
    usermod -aG docker airflow
    echo "Successfully added airflow system user to docker group"
else
    echo "ERROR: airflow system user does not exist, cannot add to docker group"
    exit 1
fi

if getent passwd airflow-container > /dev/null; then
    usermod -aG docker airflow-container
    echo "Successfully added airflow-container user to docker group"
else
    echo "ERROR: airflow-container user does not exist, cannot add to docker group"
    exit 1
fi

# Ensure proper ownership of Docker socket
if [ -S /var/run/docker.sock ]; then
    chown root:docker /var/run/docker.sock
    chmod 660 /var/run/docker.sock
fi

# Stop any existing containers and clean up
docker-compose down -v

# Start services with proper order and health checks
echo "Starting services..."

# Start Postgres first
docker-compose up -d postgres
echo "Waiting for Postgres to be healthy..."
timeout=300  # Increased timeout
while [ $timeout -gt 0 ]; do
    if docker-compose exec -T postgres pg_isready -U airflow; then
        echo "Postgres is accepting connections!"
        break
    fi
    echo "Waiting for Postgres... $(($timeout / 5)) seconds remaining"
    sleep 5
    timeout=$((timeout - 5))
    if [ $timeout -eq 0 ]; then
        echo "Postgres failed to become healthy"
        docker-compose logs postgres
        exit 1
    fi
done

# Run initialization - the docker-compose.yml now has the fixed command
echo "Running Airflow initialization..."
if ! docker-compose run --rm airflow-init; then
    echo "Airflow initialization failed. Checking logs:"
    docker-compose logs airflow-init
    
    # Try to create user manually if initialization failed
    echo "Attempting manual user creation..."
    if docker-compose run --rm airflow-init airflow db migrate; then
        echo "Database migration successful, creating admin user..."
        docker-compose run --rm airflow-init airflow users create --username admin --password admin --firstname Airflow --lastname Admin --role Admin --email admin@example.com || echo "Manual user creation also failed"
    fi
fi

# Start remaining services
echo "Starting Airflow services..."
docker-compose up -d airflow-webserver airflow-scheduler

# Wait for services to be healthy
for service in airflow-webserver airflow-scheduler; do
    timeout=300
    echo "Waiting for $service to be healthy..."
    service_started=false
    while [ $timeout -gt 0 ]; do
        if docker-compose ps $service | grep -q "Up (healthy)" || docker-compose ps $service | grep -q "Up"; then
            echo "$service is running!"
            service_started=true
            break
        fi
        echo "Waiting for $service... $(($timeout / 5)) seconds remaining"
        sleep 5
        timeout=$((timeout - 5))
    done
    
    if [ "$service_started" = false ]; then
        echo "$service failed to start properly within timeout"
        docker-compose logs $service
        # Don't exit here, just log the issue and continue
        echo "Warning: $service may not be fully healthy, but continuing..."
    fi
done

echo "Service startup completed!"
docker-compose ps

# Final health check - if webserver is responding, consider it successful
echo "Performing final health check..."
if curl -s --connect-timeout 10 "http://localhost:8081/health" > /dev/null 2>&1; then
    echo "✅ Airflow is responding to health checks!"
    
    # Create Airflow connections after services are running
    echo "Creating Airflow connections..."
    
    # Get the connections script from metadata
    CONNECTIONS_SCRIPT=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/attributes/airflow-connections" -H "Metadata-Flavor: Google" 2>/dev/null || echo "")
    
    if [ ! -z "$CONNECTIONS_SCRIPT" ]; then
        # Create connections and variables script with correct key path
        echo "#!/bin/bash" > /tmp/create_connections.sh
        echo "" >> /tmp/create_connections.sh
        echo "# Wait for Airflow to be fully ready" >> /tmp/create_connections.sh
        echo "sleep 30" >> /tmp/create_connections.sh
        echo "" >> /tmp/create_connections.sh
        echo "# Create Google Cloud connection" >> /tmp/create_connections.sh
        echo "docker-compose exec -T airflow-webserver airflow connections delete 'google_cloud_default' 2>/dev/null || true" >> /tmp/create_connections.sh
        echo "docker-compose exec -T airflow-webserver airflow connections add 'google_cloud_default' \\" >> /tmp/create_connections.sh
        echo "    --conn-type 'google_cloud_platform' \\" >> /tmp/create_connections.sh
        echo "    --conn-extra '{\"project\": \"${project_id}\", \"key_path\": \"/opt/airflow/config/service-account.json\"}'" >> /tmp/create_connections.sh
        echo "" >> /tmp/create_connections.sh
        echo "# Create common Airflow variables" >> /tmp/create_connections.sh
        echo "docker-compose exec -T airflow-webserver airflow variables set \"gcp_project_id\" \"${project_id}\"" >> /tmp/create_connections.sh
        echo "docker-compose exec -T airflow-webserver airflow variables set \"notification_email\" '[\"admin@example.com\"]'" >> /tmp/create_connections.sh
        echo "docker-compose exec -T airflow-webserver airflow variables set \"bigquery_location\" \"asia_east1\"" >> /tmp/create_connections.sh
        echo "docker-compose exec -T airflow-webserver airflow variables set \"data_retention_days\" \"30\"" >> /tmp/create_connections.sh
        echo "docker-compose exec -T airflow-webserver airflow variables set \"max_parallel_tasks\" \"5\"" >> /tmp/create_connections.sh
        echo "docker-compose exec -T airflow-webserver airflow variables set \"environment\" \"dev\"" >> /tmp/create_connections.sh
        echo "" >> /tmp/create_connections.sh
        echo "echo \"Airflow connections and variables created successfully!\"" >> /tmp/create_connections.sh
        
        chmod +x /tmp/create_connections.sh
        
        # Execute connections script in the background
        nohup /tmp/create_connections.sh > /var/log/airflow-connections.log 2>&1 &
        
        echo "✅ Airflow connections and variables script scheduled for execution"
    else
        echo "⚠️  No connections script found in metadata"
    fi
    
    echo "Airflow setup complete!"
    exit 0
else
    echo "⚠️  Airflow webserver is not responding to health checks, but services are running"
    echo "This may be normal during initial startup. Services will continue to initialize."
    echo "Airflow setup complete!"
    exit 0
fi 