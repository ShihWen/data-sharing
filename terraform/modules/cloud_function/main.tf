# Creates a GCS bucket to store the Cloud Function source code
resource "google_storage_bucket" "source_bucket" {
  name     = "${var.project_id}-cf-source"
  location = var.region
  project  = var.project_id
  uniform_bucket_level_access = true
}

# Uploads the Cloud Function source code to the GCS bucket
data "archive_file" "source_zip" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = "/tmp/${var.function_name}.zip"
}

resource "google_storage_bucket_object" "source_archive" {
  name   = "source/${var.function_name}-${data.archive_file.source_zip.output_md5}.zip"
  bucket = google_storage_bucket.source_bucket.name
  source = data.archive_file.source_zip.output_path
}

# Service account for the Cloud Function
resource "google_service_account" "function_sa" {
  account_id   = "${var.function_name}-sa"
  display_name = "Service Account for ${var.function_name} Cloud Function"
  project      = var.project_id
}

# IAM policy for the Cloud Function service account
resource "google_project_iam_member" "function_sa_secret_accessor" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.function_sa.email}"
}

resource "google_project_iam_member" "function_sa_storage_admin" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.function_sa.email}"
}

# Cloud Function resource
resource "google_cloudfunctions2_function" "function" {
  name     = var.function_name
  location = var.region
  project  = var.project_id

  build_config {
    runtime     = "python310"
    entry_point = var.entry_point
    source {
      storage_source {
        bucket = google_storage_bucket.source_bucket.name
        object = google_storage_bucket_object.source_archive.name
      }
    }
  }

  service_config {
    max_instance_count  = 1
    min_instance_count  = 0
    available_memory    = "256Mi"
    timeout_seconds     = 60
    environment_variables = var.environment_variables
    service_account_email = google_service_account.function_sa.email
  }

  depends_on = [
    google_project_iam_member.function_sa_secret_accessor,
    google_project_iam_member.function_sa_storage_admin
  ]
}

# Allows the Cloud Function to be invoked by Cloud Scheduler or other services
resource "google_cloud_run_service_iam_member" "invoker" {
  location = google_cloudfunctions2_function.function.location
  project  = google_cloudfunctions2_function.function.project
  service  = google_cloudfunctions2_function.function.name
  role     = "roles/run.invoker"
  member   = var.invoker_service_account_email
} 