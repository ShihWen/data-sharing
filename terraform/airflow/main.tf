provider "google" {
  project = var.project_id
  region  = var.region
}

# Create service account for Airflow
resource "google_service_account" "airflow_sa" {
  account_id   = "airflow-service-account"
  display_name = "Airflow Service Account"
  description  = "Service account for Airflow operations"
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
}

# Create Cloud Scheduler job for starting Airflow VM
resource "google_cloud_scheduler_job" "start_airflow" {
  name        = "start-airflow-vm"
  description = "Start Airflow VM on Saturday morning"
  schedule    = "0 8 * * 6"  # Every Saturday at 8:00 AM
  time_zone   = "Asia/Taipei"
  region      = var.region

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

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
      size  = 25
    }
  }

  # Add startup script
  metadata_startup_script = <<-EOF
    #!/bin/bash
    
    # Install Docker
    apt-get update
    apt-get install -y apt-transport-https ca-certificates curl software-properties-common
    curl -fsSL https://download.docker.com/linux/debian/gpg | apt-key add -
    add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/debian $(lsb_release -cs) stable"
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io

    # Install Docker Compose
    curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose

    # Create Airflow directories
    mkdir -p /opt/airflow/{dags,logs,config,plugins}

    # Pull Airflow configurations from GCS
    gsutil -m cp -r gs://${google_storage_bucket.airflow_bucket.name}/docker/* /opt/airflow/

    # Start Airflow services
    cd /opt/airflow
    docker-compose up -d
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