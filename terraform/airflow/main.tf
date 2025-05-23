# Create service account for Airflow
resource "google_service_account" "airflow_sa" {
  account_id   = "airflow-service-account"
  display_name = "Airflow Service Account"
  description  = "Service account for Airflow operations"
}

# Create Secret Manager secret for service account key
resource "google_secret_manager_secret" "airflow_sa_key" {
  secret_id = "airflow-service-account-key"
  
  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
}

# Grant access to Secret Manager secret
resource "google_secret_manager_secret_iam_member" "secret_access" {
  secret_id = google_secret_manager_secret.airflow_sa_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.airflow_sa.email}"
}

# Add Secret Manager access role to service account
resource "google_project_iam_member" "airflow_sa_secretmanager" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.airflow_sa.email}"
}

# Grant necessary roles to the service account
resource "google_project_iam_member" "airflow_sa_roles" {
  for_each = toset([
    "roles/storage.objectViewer",
    "roles/bigquery.dataViewer",
    "roles/bigquery.jobUser",
    "roles/logging.logWriter"
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.airflow_sa.email}"
}

# Create service account for Cloud Scheduler
resource "google_service_account" "scheduler_sa" {
  account_id   = "airflow-scheduler-sa"
  display_name = "Airflow Scheduler Service Account"
  description  = "Service account for starting/stopping Airflow VM"
}

# Grant necessary roles to the scheduler service account
resource "google_project_iam_member" "scheduler_sa_roles" {
  for_each = toset([
    "roles/compute.instanceAdmin.v1",
    "roles/logging.logWriter"
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.scheduler_sa.email}"
  depends_on = [google_service_account.scheduler_sa]
}

# Create Cloud Scheduler job for starting Airflow VM
resource "google_cloud_scheduler_job" "start_airflow" {
  name        = "start-airflow-vm"
  description = "Start Airflow VM on Saturday morning"
  schedule    = "0 8 * * 6"  # Every Saturday at 8:00 AM
  time_zone   = "Asia/Taipei"
  region      = var.region
  depends_on  = [google_service_account.scheduler_sa, google_project_iam_member.scheduler_sa_roles]

  http_target {
    http_method = "POST"
    uri         = "https://compute.googleapis.com/compute/v1/projects/${var.project_id}/zones/${var.zone}/instances/${google_compute_instance.airflow.name}/start"
    oauth_token {
      service_account_email = google_service_account.scheduler_sa.email
    }
  }
}

# Create Cloud Scheduler job for stopping Airflow VM
resource "google_cloud_scheduler_job" "stop_airflow" {
  name        = "stop-airflow-vm"
  description = "Stop Airflow VM on Sunday midnight"
  schedule    = "0 0 * * 0"  # Every Sunday at 00:00
  time_zone   = "Asia/Taipei"
  region      = var.region
  depends_on  = [google_service_account.scheduler_sa, google_project_iam_member.scheduler_sa_roles]

  http_target {
    http_method = "POST"
    uri         = "https://compute.googleapis.com/compute/v1/projects/${var.project_id}/zones/${var.zone}/instances/${google_compute_instance.airflow.name}/stop"
    oauth_token {
      service_account_email = google_service_account.scheduler_sa.email
    }
  }
}

# Basic VM for Airflow
resource "google_compute_instance" "airflow" {
  name         = "airflow-vm"
  machine_type = "e2-small"
  zone         = var.zone

  lifecycle {
    prevent_destroy = false
    ignore_changes = [
      metadata_startup_script,
      boot_disk,
    ]
  }

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
      size  = 25
    }
  }

  # Add startup script
  metadata_startup_script = <<-EOF
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
    
    AIRFLOW_UID=$(id -u airflow)
    AIRFLOW_GID=$(id -g airflow)

    # Pull Airflow configurations from GCS
    echo "Pulling configurations from GCS..."
    cd /opt/airflow
    gsutil -m cp -r gs://${google_storage_bucket.airflow_bucket.name}/docker/* .

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
    
    # Create environment file with explicit database connection
    cat > .env <<EOL
    AIRFLOW_UID=$AIRFLOW_UID
    AIRFLOW_GID=$AIRFLOW_GID
    AIRFLOW_FERNET_KEY=$FERNET_KEY
    AIRFLOW_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(16))")
    AIRFLOW_GCS_BUCKET=${google_storage_bucket.airflow_bucket.name}
    GOOGLE_CLOUD_PROJECT=${var.project_id}
    AIRFLOW_ADMIN_USER=admin
    AIRFLOW_ADMIN_PASSWORD=admin
    AIRFLOW_ADMIN_FIRSTNAME=Admin
    AIRFLOW_ADMIN_LASTNAME=User
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
    usermod -aG airflow $USER

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

    # Run initialization
    echo "Running Airflow initialization..."
    if ! docker-compose up --exit-code-from airflow-init airflow-init; then
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
    EOF

  # Attach the service account to the VM
  service_account {
    email  = google_service_account.airflow_sa.email
    scopes = ["cloud-platform"]
  }

  network_interface {
    network = "default"
    access_config {
      // Ephemeral public IP
    }
  }

  # Allow stopping/starting the instance
  scheduling {
    preemptible       = false
    automatic_restart = false
  }

  tags = ["airflow"]
}

# Create firewall rule for Airflow webserver
resource "google_compute_firewall" "airflow_webserver" {
  name    = "allow-airflow-webserver"
  network = "default"

  allow {
    protocol = "tcp"
    ports    = ["8081"]  # Updated port for Airflow
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["airflow"]
}

# Create GCS bucket for Airflow logs and DAGs
resource "google_storage_bucket" "airflow_bucket" {
  name          = "${var.project_id}-airflow-storage"
  location      = var.region
  force_destroy = true

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 30  # Days
    }
    action {
      type = "Delete"
    }
  }

  # Enable backup retention
  retention_policy {
    is_locked = false
    retention_period = 2592000 # 30 days in seconds
  }
}

# Grant the service account access to the bucket
resource "google_storage_bucket_iam_member" "airflow_bucket_access" {
  bucket = google_storage_bucket.airflow_bucket.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.airflow_sa.email}"
} 