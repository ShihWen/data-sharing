resource "google_project_service" "enable_transfer" {
  project = var.project_id
  service = "bigquerydatatransfer.googleapis.com"
}

# Enable Secret Manager API
resource "google_project_service" "enable_secretmanager" {
  project = var.project_id
  service = "secretmanager.googleapis.com"
}

# Create a secret for AWS credentials
resource "google_secret_manager_secret" "aws_credentials" {
  secret_id = "aws-s3-credentials-${var.bronze_dataset_id}"  # Make secret name unique per dataset
  project   = var.project_id

  replication {
    auto {}  # Use auto instead of automatic = true
  }

  depends_on = [google_project_service.enable_secretmanager]
}

resource "google_secret_manager_secret_version" "aws_credentials_version" {
  secret = google_secret_manager_secret.aws_credentials.id

  secret_data = jsonencode({
    access_key_id     = var.aws_access_key
    secret_access_key = var.aws_secret_key
  })
}

# Transfer job for MRT Traffic data
resource "google_bigquery_data_transfer_config" "mrt_traffic_transfer" {
  depends_on = [google_project_service.enable_transfer]

  display_name           = "MRT Traffic Data Transfer"
  project               = var.project_id
  location              = "asia-east1"
  data_source_id        = "amazon_s3"
  schedule              = var.schedule
  destination_dataset_id = var.bronze_dataset_id
  disabled              = false

  params = {
    destination_table_name_template = "mrt_traffic"
    data_path                      = "s3://${var.s3_bucket}/mrt-traffic/*.parquet"
    access_key_id                  = var.aws_access_key
    secret_access_key              = var.aws_secret_key
    file_format                    = "PARQUET"
    max_bad_records               = 0
    write_disposition             = "WRITE_APPEND"
  }
}

# Transfer job for MRT Station data
resource "google_bigquery_data_transfer_config" "mrt_station_transfer" {
  depends_on = [google_project_service.enable_transfer]

  display_name           = "MRT Station Data Transfer"
  project               = var.project_id
  location              = "asia-east1"
  data_source_id        = "amazon_s3"
  schedule              = var.schedule
  destination_dataset_id = var.bronze_dataset_id
  disabled              = false

  params = {
    destination_table_name_template = "mrt_station"
    data_path                      = "s3://${var.s3_bucket}/mrt-station/mrt_station*.parquet"
    access_key_id                  = var.aws_access_key
    secret_access_key              = var.aws_secret_key
    file_format                    = "PARQUET"
    max_bad_records               = 0
    write_disposition             = "WRITE_APPEND"
  }
}

# Transfer job for MRT Exit data
resource "google_bigquery_data_transfer_config" "mrt_exit_transfer" {
  depends_on = [google_project_service.enable_transfer]

  display_name           = "MRT Exit Data Transfer"
  project               = var.project_id
  location              = "asia-east1"
  data_source_id        = "amazon_s3"
  schedule              = var.schedule
  destination_dataset_id = var.bronze_dataset_id
  disabled              = false

  params = {
    destination_table_name_template = "mrt_exit"
    data_path                      = "s3://${var.s3_bucket}/mrt-station/mrt_exit*.parquet"
    access_key_id                  = var.aws_access_key
    secret_access_key              = var.aws_secret_key
    file_format                    = "PARQUET"
    max_bad_records               = 0
    write_disposition             = "WRITE_APPEND"
  }
} 