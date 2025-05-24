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

# Create Airflow directories with proper permissions
echo "Creating Airflow directories..."
mkdir -p /opt/airflow/{dags,logs,config,plugins}

# Set up Airflow user and group if they don't exist
if ! getent group airflow > /dev/null; then
    groupadd --system airflow
fi
if ! getent passwd airflow > /dev/null; then
    useradd --system --home-dir /opt/airflow --no-create-home --shell /bin/false --gid airflow airflow
fi

# Set fixed UID/GID for Airflow user
AIRFLOW_UID=50000
AIRFLOW_GID=0

# Pull Airflow configurations from GCS
echo "Pulling configurations from GCS..."
cd /opt/airflow
gsutil -m cp -r gs://${gcs_bucket}/docker/* .

# Set up GCS sync service
echo "Setting up GCS sync service..."
cat > /etc/systemd/system/gcs-sync.service <<EOL
[Unit]
Description=GCS DAGs Sync Service
After=network.target

[Service]
Type=simple
User=airflow
Group=airflow
ExecStart=/usr/bin/gsutil -m rsync -r gs://${gcs_bucket}/docker/dags/ /opt/airflow/dags/
Restart=always
RestartSec=60

[Install]
WantedBy=multi-user.target
EOL

# Enable and start GCS sync service
systemctl daemon-reload
systemctl enable gcs-sync.service
systemctl start gcs-sync.service

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

# Set proper permissions
chown -R airflow:airflow /opt/airflow
chmod -R 755 /opt/airflow/dags
chmod -R 755 /opt/airflow/logs
chmod -R 755 /opt/airflow/plugins
chmod 600 /opt/airflow/config/airflow.cfg
chmod 644 /opt/airflow/config/service-account.json
chown airflow:airflow /opt/airflow/config/service-account.json

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

chmod 600 .env
chown $AIRFLOW_UID:$AIRFLOW_GID .env

# Set proper permissions for service account file
chmod 644 /opt/airflow/config/service-account.json
chown $AIRFLOW_UID:0 /opt/airflow/config/service-account.json

# Add current user to docker group and airflow group
usermod -aG docker airflow
if [ -n "$USER" ]; then
  usermod -aG airflow $USER
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

# Run initialization with proper command structure
echo "Running Airflow initialization..."
if ! docker-compose run --rm airflow-init bash -c '
    airflow db init &&
    airflow users create \
        -u admin \
        -p admin \
        -f Airflow \
        -l Admin \
        -r Admin \
        -e admin@example.com
'; then
    echo "Airflow initialization failed. Checking logs:"
    docker-compose logs airflow-init
    exit 1
fi

# Start remaining services
echo "Starting Airflow services..."
docker-compose up -d airflow-webserver airflow-scheduler

# Wait for services to be healthy
for service in airflow-webserver airflow-scheduler; do
    timeout=300
    echo "Waiting for $service to be healthy..."
    while [ $timeout -gt 0 ]; do
        if docker-compose ps $service | grep -q "Up (healthy)"; then
            echo "$service is healthy!"
            break
        fi
        echo "Waiting for $service... $(($timeout / 5)) seconds remaining"
        sleep 5
        timeout=$((timeout - 5))
        if [ $timeout -eq 0 ]; then
            echo "$service failed to become healthy"
            docker-compose logs $service
            exit 1
        fi
    done
done

echo "All services are running and healthy!"
docker-compose ps
echo "Airflow setup complete!" 