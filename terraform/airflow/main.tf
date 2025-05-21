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

  tags = ["airflow"]
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
}

# Grant the service account access to the bucket
resource "google_storage_bucket_iam_member" "airflow_bucket_access" {
  bucket = google_storage_bucket.airflow_bucket.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.airflow_sa.email}"
} 