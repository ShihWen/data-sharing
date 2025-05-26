#!/bin/bash
cd /opt/airflow

# Generate keys
FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(16))")

# Create .env file
cat > .env << EOF
AIRFLOW_UID=50000
AIRFLOW_GID=0
AIRFLOW_FERNET_KEY=$FERNET_KEY
AIRFLOW_SECRET_KEY=$SECRET_KEY
AIRFLOW_GCS_BUCKET=open-data-v2-cicd-airflow-storage
GOOGLE_CLOUD_PROJECT=open-data-v2-cicd
AIRFLOW_ADMIN_USER=admin
AIRFLOW_ADMIN_PASSWORD=admin
AIRFLOW_ADMIN_FIRSTNAME=Airflow
AIRFLOW_ADMIN_LASTNAME=Admin
AIRFLOW_ADMIN_EMAIL=admin@example.com
AIRFLOW_DB_CONNECTION=postgresql+psycopg2://airflow:airflow@postgres/airflow
EOF

# Set proper permissions
chown 50000:0 .env
chmod 600 .env

echo "Environment file created successfully"
echo "Starting Airflow services..."

# Start services
docker-compose up -d

echo "Services started. Checking status..."
sleep 10
docker-compose ps 