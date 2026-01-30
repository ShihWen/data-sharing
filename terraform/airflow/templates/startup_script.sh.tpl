#!/bin/bash
set -e  # Exit on error

echo "Starting Airflow setup..."

# Fix potentially broken Debian backports repository to prevent apt-get update failures.
# This changes the source list to point to the official archive for older releases.
echo "deb http://archive.debian.org/debian bullseye-backports main" > /etc/apt/sources.list.d/backports.list

# Install Docker
apt-get update -o Acquire::Check-Valid-Until=false
# Fix any interrupted dpkg operations
echo "Attempting to fix interrupted dpkg operations..."
dpkg --configure -a || echo "WARNING: dpkg --configure -a failed or found nothing to do."
echo "dpkg operation fix attempt complete."
apt-get install -y apt-transport-https ca-certificates curl software-properties-common python3-pip
curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add -
add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_release -cs) stable"
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io


# --- FIX START: Configure Docker to accept older clients ---
# Docker v29+ raised the minimum API version to 1.44, breaking compatibility with older docker-compose.
# We explicitly set the minimum API version to 1.32 to allow docker-compose v2.20 to work.
echo '{"min-api-version": "1.32"}' > /etc/docker/daemon.json
systemctl restart docker
# --- FIX END ---


# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# --- NEW: Docker Hub Authentication ---
echo "Fetching Docker Hub credentials from Secret Manager..."
DOCKER_USERNAME=$(gcloud secrets versions access latest --secret="dockerhub-username" --project="${project_id}" 2>/dev/null)
DOCKER_ACCESS_TOKEN=$(gcloud secrets versions access latest --secret="dockerhub-access-token" --project="${project_id}" 2>/dev/null)

if [ -z "$DOCKER_USERNAME" ] || [ -z "$DOCKER_ACCESS_TOKEN" ]; then
    echo "WARNING: Docker Hub credentials not found in Secret Manager. Docker image pulls might fail due to rate limits."
else
    echo "Logging into Docker Hub..."
    MAX_RETRIES=5
    RETRY_COUNT=0
    until [ $RETRY_COUNT -ge $MAX_RETRIES ]; do
        echo "Attempting Docker login (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)..."
        echo "$DOCKER_ACCESS_TOKEN" | docker login --username "$DOCKER_USERNAME" --password-stdin && break
        RETRY_COUNT=$((RETRY_COUNT + 1))
        echo "Docker login failed. Retrying in 10 seconds..."
        sleep 10
    done

    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "ERROR: Failed to log into Docker Hub after $MAX_RETRIES attempts."
        exit 1
    else
        echo "SUCCESS: Logged into Docker Hub."
    fi
fi
# --- END NEW: Docker Hub Authentication ---

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
gsutil cp -r gs://${gcs_bucket}/docker/* .

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
ExecStart=/usr/bin/gsutil rsync -r -d gs://${gcs_bucket}/docker/dags/ /opt/airflow/dags/
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
echo "SUCCESS: Airflow permissions service enabled for future boots"

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
set -x
docker-compose down -v 2>&1 | tee -a /var/log/docker-compose.log
set +x

# Start services with proper order and health checks
echo "Starting services..."

# Start Postgres first
set -x
docker-compose up -d postgres 2>&1 | tee -a /var/log/docker-compose.log
set +x
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
        set -x
        docker-compose logs postgres 2>&1 | tee -a /var/log/docker-compose.log
        set +x
        exit 1
    fi
done

# Run initialization - the docker-compose.yml now has the fixed command
echo "Running Airflow initialization..."
set -x
if ! docker-compose run --rm airflow-init 2>&1 | tee -a /var/log/docker-compose.log; then
    set +x
    echo "Airflow initialization failed. Checking logs:"
    set -x
    docker-compose logs airflow-init 2>&1 | tee -a /var/log/docker-compose.log
    set +x
    
    # Try to create user manually if initialization failed
    echo "Attempting manual user creation..."
    set -x
    if docker-compose run --rm airflow-init airflow db migrate 2>&1 | tee -a /var/log/docker-compose.log; then
        set +x
        echo "Database migration successful, creating admin user..."
        set -x
        docker-compose run --rm airflow-init airflow users create --username admin --password admin --firstname Airflow --lastname Admin --role Admin --email admin@example.com 2>&1 | tee -a /var/log/docker-compose.log || echo "Manual user creation also failed" 2>&1 | tee -a /var/log/docker-compose.log
        set +x
    fi
fi
set +x

# Start remaining services
echo "Starting Airflow services..."
set -x
docker-compose up -d airflow-webserver airflow-scheduler 2>&1 | tee -a /var/log/docker-compose.log
set +x

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
        set -x
        docker-compose logs $service 2>&1 | tee -a /var/log/docker-compose.log
        set +x
        # Don't exit here, just log the issue and continue
        echo "Warning: $service may not be fully healthy, but continuing..."
    fi
done

echo "Service startup completed!"
set -x
docker-compose ps 2>&1 | tee -a /var/log/docker-compose.log
set +x

# Final health check - if webserver is responding, consider it successful
echo "Performing final health check..."

# Wait for Airflow to be fully ready with comprehensive health checks
echo "Waiting for Airflow to be fully operational..."
timeout=600  # 10 minutes total timeout
airflow_ready=false

while [ $timeout -gt 0 ]; do
    echo "Checking Airflow readiness... $(($timeout / 30)) checks remaining"
    
    # Check if webserver is responding
    if curl -s --connect-timeout 10 "http://localhost:8081/health" > /dev/null 2>&1; then
        echo "SUCCESS: Webserver is responding to health checks"
        
        # Check if scheduler is healthy
        if docker-compose ps airflow-scheduler | grep -q "Up (healthy)" || docker-compose ps airflow-scheduler | grep -q "Up"; then
            echo "SUCCESS: Scheduler is running"
            
            # Check if we can actually execute Airflow commands
            if docker-compose exec -T airflow-webserver airflow version > /dev/null 2>&1; then
                echo "SUCCESS: Airflow CLI is working"
                
                # Test if we can access the database
                if docker-compose exec -T airflow-webserver airflow db check > /dev/null 2>&1; then
                    echo "SUCCESS: Database connection is working"
                    airflow_ready=true
                    break
                else
                    echo "WARNING: Database connection not ready yet..."
                fi
            else
                echo "WARNING: Airflow CLI not ready yet..."
            fi
        else
            echo "WARNING: Scheduler not ready yet..."
        fi
    else
        echo "WARNING: Webserver not responding yet..."
    fi
    
    sleep 30
    timeout=$((timeout - 30))
done

if [ "$airflow_ready" = true ]; then
    echo "SUCCESS: Airflow is fully operational and ready!"
    
    # Setup automatic connections creation using existing airflow-manager.sh script
    echo "Setting up automatic Airflow connections service..."
    
    # Download airflow-manager.sh from GCS bucket
    echo "Downloading airflow-manager.sh script..."
    if gsutil cp gs://${gcs_bucket}/scripts/airflow-manager.sh /opt/airflow/airflow-manager.sh; then
        chmod +x /opt/airflow/airflow-manager.sh
        chown $AIRFLOW_UID:$AIRFLOW_GID /opt/airflow/airflow-manager.sh
        echo "SUCCESS: Downloaded airflow-manager.sh script"
    else
        echo "WARNING: Could not download airflow-manager.sh, creating minimal connections script"
        # Create a comprehensive fallback script that includes variables and connections
        cat > /opt/airflow/create_connections_fallback.sh <<'FALLBACK_EOF'
#!/bin/bash
set -e
echo "Creating comprehensive Airflow connections and variables..."

cd /opt/airflow

# Wait for Airflow services to stabilize
echo "Waiting for Airflow services to stabilize..."
sleep 15

# Create Google Cloud connection
echo "Creating Google Cloud connection..."
docker-compose exec -T airflow-webserver airflow connections delete 'google_cloud_default' 2>/dev/null || true
docker-compose exec -T airflow-webserver airflow connections add 'google_cloud_default' \
    --conn-type 'google_cloud_platform' \
    --conn-extra '{"project": "${project_id}", "key_path": "/opt/airflow/config/service-account.json"}'

if docker-compose exec -T airflow-webserver airflow connections get 'google_cloud_default' > /dev/null 2>&1; then
    echo "SUCCESS: Google Cloud connection created successfully!"
else
    echo "ERROR: Failed to create Google Cloud connection"
    exit 1
fi

echo ""
echo "Creating Airflow variables..."

# Create all the essential variables
variables_to_set=(
    "gcp_project_id ${project_id}"
    "gcp_region asia-east1"
    "notification_email '[\"admin@example.com\"]'"
    "bigquery_location asia-east1"
    "data_retention_days 30"
    "max_parallel_tasks 5"
    "environment dev"
    "tpe_mrt_bronze_dataset_id tpe_mrt_bronze"
    "tpe_mrt_silver_dataset_id tpe_mrt_silver"
    "tpe_mrt_gold_dataset_id tpe_mrt_gold"
    "gcs_data_lake_bucket open-data-v2-cicd-data-lake"
    "mrt_station_ntmc_function_uri https://asia-east1-open-data-v2-cicd.cloudfunctions.net/mrt-station-ntmc-fetcher"
    "paused_dags_list mrt_traffic_bronze_to_silver_full_load,reference_boundaries_city_source_to_silver,reference_boundaries_town_source_to_silver,reference_boundaries_village_source_to_silver,mrt_station_ntmc_source_to_bronze,tdx_railway_station_source_to_silver,tdx_intercity_bus_station_source_to_silver,tdx_intercity_bus_shape_source_to_silver,tdx_city_bus_shape_source_to_silver,tdx_city_bus_station_source_to_silver,tdx_mrt_shape_source_to_silver"
)

for var_pair in "$${variables_to_set[@]}"; do
    read -r key value <<<"$$var_pair"
    echo "Processing variable: $$key"

    current_value=$(docker-compose exec -T airflow-webserver airflow variables get "$key" 2>/dev/null || echo "__VAR_NOT_FOUND__") # Get current value, or a special string if not found

    if [ "$current_value" = "__VAR_NOT_FOUND__" ]; then
        echo "Variable $$key does not exist, setting initial value to: $$value"
        if docker-compose exec -T airflow-webserver airflow variables set "$key" "$value"; then
            echo "SUCCESS: Set variable: $$key"
        else
            echo "ERROR: Failed to set variable: $$key"
        fi
    elif [ "$current_value" != "$value" ]; then
        echo "Variable $$key value changed from '$current_value' to '$value', updating."
        if docker-compose exec -T airflow-webserver airflow variables set "$key" "$value"; then
            echo "SUCCESS: Updated variable: $$key"
        else
            echo "ERROR: Failed to update variable: $$key"
        fi
    else
        echo "Variable $$key already exists with the same value, skipping update."
    fi
done

# Try to get TDX credentials from Secret Manager if available
echo ""
echo "Setting TDX credentials from Secret Manager..."
if command -v gcloud >/dev/null 2>&1; then
    # Get TDX client ID
    if tdx_client_id=$$(gcloud secrets versions access latest --secret=tdx_client_id 2>/dev/null); then
        if docker-compose exec -T airflow-webserver airflow variables set "tdx_client_id" "$tdx_client_id"; then
            echo "SUCCESS: Set variable: tdx_client_id"
        else
            echo "ERROR: Failed to set variable: tdx_client_id"
        fi
    else
        echo "WARNING: Could not retrieve tdx_client_id from Secret Manager"
    fi
    
    # Get TDX client secret
    if tdx_client_secret=$$(gcloud secrets versions access latest --secret=tdx_client_secret 2>/dev/null); then
        if docker-compose exec -T airflow-webserver airflow variables set "tdx_client_secret" "$tdx_client_secret"; then
            echo "SUCCESS: Set variable: tdx_client_secret"
        else
            echo "ERROR: Failed to set variable: tdx_client_secret"
        fi
    else
        echo "WARNING: Could not retrieve tdx_client_secret from Secret Manager"
    fi
else
    echo "WARNING: gcloud command not available, skipping TDX credentials"
fi

echo ""
echo "SUCCESS: Comprehensive connections and variables setup completed!"

# Unpause all DAGs except specific ones that should remain paused
echo ""
echo "Unpausing DAGs (keeping mrt_traffic_bronze_to_silver_full_load paused)..."

# Get list of all DAGs and unpause them individually (compatible with older Airflow versions)
echo "Getting list of all DAGs..."
dag_list=$(docker-compose exec -T airflow-webserver airflow dags list --output table 2>/dev/null | grep -v "dag_id" | awk '{print $1}' | grep -v "^$" || echo "")

if [ -n "$dag_list" ]; then
    echo "Found DAGs: $dag_list"
    unpause_success_count=0
    unpause_total_count=0
    
    for dag_id in $dag_list; do
        # Skip the DAG that should remain paused
        if [ "$dag_id" = "mrt_traffic_bronze_to_silver_full_load" ]; then
            echo "Skipping mrt_traffic_bronze_to_silver_full_load DAG (keeping it paused)"
            continue
        fi
        
        echo "Unpausing DAG: $dag_id"
        if docker-compose exec -T airflow-webserver airflow dags unpause "$dag_id" >/dev/null 2>&1; then
            echo "SUCCESS: Unpaused DAG: $dag_id"
            unpause_success_count=$((unpause_success_count + 1))
        else
            echo "WARNING: Failed to unpause DAG: $dag_id"
        fi
        unpause_total_count=$((unpause_total_count + 1))
    done
    
    echo "SUCCESS: Unpaused $unpause_success_count out of $unpause_total_count DAGs"
    
    # Ensure the specific DAG remains paused
    echo "Ensuring mrt_traffic_bronze_to_silver_full_load DAG remains paused..."
    if docker-compose exec -T airflow-webserver airflow dags pause mrt_traffic_bronze_to_silver_full_load >/dev/null 2>&1; then
        echo "SUCCESS: mrt_traffic_bronze_to_silver_full_load DAG is confirmed paused"
    else
        echo "WARNING: Could not confirm pause status for mrt_traffic_bronze_to_silver_full_load DAG"
    fi
else
    echo "WARNING: Could not retrieve DAG list, skipping DAG unpausing"
fi

FALLBACK_EOF
        chmod +x /opt/airflow/create_connections_fallback.sh
        chown $AIRFLOW_UID:$AIRFLOW_GID /opt/airflow/create_connections_fallback.sh
    fi
    
    # Create systemd service for automatic connections creation
    cat > /etc/systemd/system/airflow-connections.service <<EOL
[Unit]
Description=Create Airflow Connections and Variables using airflow-manager.sh
After=multi-user.target
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
User=root
WorkingDirectory=/opt/airflow
Environment="PROJECT_ID=${project_id}"
Environment="ZONE=asia-east1-b"
Environment="VM_NAME=airflow-vm"
Environment="BUCKET_NAME=${gcs_bucket}"
ExecStartPre=/bin/bash -c 'timeout=600; while [ \$timeout -gt 0 ]; do if curl -s --connect-timeout 5 "http://localhost:8081/health" > /dev/null 2>&1; then echo "Airflow is ready"; break; fi; echo "Waiting for Airflow... \$((\$timeout / 30)) checks remaining"; sleep 30; timeout=\$((\$timeout - 30)); done'
ExecStart=/bin/bash -c 'if [ -f /opt/airflow/airflow-manager.sh ]; then /opt/airflow/airflow-manager.sh connections; else /opt/airflow/create_connections_fallback.sh; fi'
StandardOutput=journal
StandardError=journal
RemainAfterExit=yes
TimeoutStartSec=900

[Install]
WantedBy=multi-user.target
EOL

    # Enable the connections service
    systemctl daemon-reload
    systemctl enable airflow-connections.service
            echo "SUCCESS: Airflow connections service enabled for automatic execution on boot"
    
    # Execute connections creation now (synchronously to ensure completion)
    echo "Creating connections and variables now..."
    if [ -f /opt/airflow/airflow-manager.sh ]; then
        echo "Running airflow-manager.sh connections..."
        if /opt/airflow/airflow-manager.sh connections; then
            echo "SUCCESS: Successfully created connections and variables using airflow-manager.sh"
            
            # Pausing specific DAGs as defined in Airflow variables
            paused_dags_string=$(docker-compose exec -T airflow-webserver airflow variables get paused_dags_list)
            if [ -n "$paused_dags_string" ]; then
                # Split the comma-separated string into an array
                IFS=',' read -r -a paused_dags_array <<< "$paused_dags_string"

                echo ""
                echo "Unpausing DAGs (keeping specified DAGs paused from variable)..."

                # Get list of all DAGs and unpause them individually
                echo "Getting list of all DAGs..."
                dag_list=$(docker-compose exec -T airflow-webserver airflow dags list --output table 2>/dev/null | grep -v "^$" | tail -n +2 | awk '{print $1}' || echo "")

                if [ -n "$dag_list" ]; then
                    echo "Found DAGs: $dag_list"
                    echo "DAGs that will remain paused (from variable): $${paused_dags_array[*]}"
                    unpause_success_count=0
                    unpause_total_count=0

                    for dag_id in $dag_list; do
                        # Check if this DAG should remain paused
                        should_skip=false
                        for paused_dag in "$${paused_dags_array[@]}"; do
                            if [ "$dag_id" = "$paused_dag" ]; then
                                echo "Skipping $paused_dag DAG (keeping it paused)"
                                should_skip=true
                                break
                            fi
                        done

                        if [ "$should_skip" = true ]; then
                            continue
                        fi

                        echo "Unpausing DAG: $dag_id"
                        if docker-compose exec -T airflow-webserver airflow dags unpause "$dag_id" >/dev/null 2>&1; then
                            echo "SUCCESS: Unpaused DAG: $dag_id"
                            unpause_success_count=$((unpause_success_count + 1))
                        else
                            echo "WARNING: Failed to unpause DAG: $dag_id"
                        fi
                        unpause_total_count=$((unpause_total_count + 1))
                    done

                    echo "SUCCESS: Unpaused $unpause_success_count out of $unpause_total_count DAGs"

                    # Ensure all specified DAGs remain paused
                    echo "Ensuring specified DAGs remain paused..."
                    for paused_dag in "$${paused_dags_array[@]}"; do
                        if docker-compose exec -T airflow-webserver airflow dags pause "$paused_dag" >/dev/null 2>&1; then
                            echo "SUCCESS: $paused_dag DAG is confirmed paused"
                        else
                            echo "WARNING: Could not confirm pause status for $paused_dag DAG"
                        fi
                    done
                else
                    echo "WARNING: Could not retrieve DAG list, skipping DAG unpausing"
                fi
            else
                echo "No DAGs specified in 'paused_dags_list' Airflow variable to pause."
            fi
        else
            echo "WARNING: airflow-manager.sh failed, trying fallback script..."
            if /opt/airflow/create_connections_fallback.sh; then
                echo "SUCCESS: Successfully created comprehensive connections and variables using fallback script"
            else
                echo "ERROR: Both scripts failed to create connections"
            fi
        fi
    else
        echo "Running fallback connections script..."
        if /opt/airflow/create_connections_fallback.sh; then
            echo "SUCCESS: Successfully created comprehensive connections and variables using fallback script"
        else
            echo "ERROR: Fallback script failed to create connections"
        fi
    fi
    
    echo "SUCCESS: Airflow setup complete with connections and variables configured!"
    exit 0
else
    echo "ERROR: Airflow failed to become fully operational within timeout"
    echo "Services may still be initializing. The connections service will automatically create connections when Airflow becomes ready."
    echo "Current service status:"
    docker-compose ps
    echo "Airflow setup complete, but connections will be created when services are ready."
    exit 0
fi 