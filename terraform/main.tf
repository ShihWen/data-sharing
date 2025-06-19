provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable necessary APIs
resource "google_project_service" "enable_secretmanager" {
  project            = var.project_id
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "enable_transfer" {
  project            = var.project_id
  service            = "bigquerydatatransfer.googleapis.com"
  disable_on_destroy = false
}

# Get project information
data "google_project" "current" {
  project_id = var.project_id
}

locals {
  datasets = yamldecode(file("${path.module}/bigquery_datasets/config/datasets.yaml")).datasets
  
  # Create a map of all dataset IDs to their module outputs
  dataset_outputs = {
    for ds in local.datasets : ds.id => module.bigquery_datasets[ds.id].dataset_id
  }

  transfer_jobs = {
    mrt_traffic = {
      display_name        = "MRT Traffic Data Transfer"
      destination_table   = "mrt_traffic"
      data_path           = "s3://${var.s3_bucket}/mrt-traffic/*.parquet"
      destination_dataset = "tpe_mrt_bronze"
    }
    mrt_station = {
      display_name        = "MRT Station Data Transfer"
      destination_table   = "mrt_station"
      data_path           = "s3://${var.s3_bucket}/mrt-station/mrt_station*"
      destination_dataset = "tpe_mrt_bronze"
    }
    mrt_exit = {
      display_name        = "MRT Exit Data Transfer"
      destination_table   = "mrt_exit"
      data_path           = "s3://${var.s3_bucket}/mrt-station/mrt_exit*"
      destination_dataset = "tpe_mrt_bronze"
    }
  }
}

# Create a single service account for all transfer jobs
resource "google_service_account" "transfer_sa" {
  account_id   = "bigquery-transfer-sa"
  display_name = "BigQuery Transfer Service Account"
  project      = var.project_id
}

# Grant necessary roles to the transfer service account
resource "google_project_iam_member" "transfer_sa_roles" {
  for_each = toset([
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/storage.objectViewer",
    "roles/secretmanager.secretAccessor"  # Grant access to Secret Manager
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.transfer_sa.email}"
}

# Create a single secret for AWS credentials
resource "google_secret_manager_secret" "aws_credentials" {
  secret_id = "aws-s3-credentials-for-mrt"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.enable_secretmanager]
}

resource "google_secret_manager_secret_version" "aws_credentials_version" {
  secret      = google_secret_manager_secret.aws_credentials.id
  secret_data = jsonencode({
    access_key_id     = var.aws_access_key
    secret_access_key = var.aws_secret_key
  })
}

module "airflow" {
  source = "./airflow"

  project_id   = var.project_id
  region       = var.region
  zone         = var.zone
  depends_on = [google_project_service.enable_secretmanager]
}

module "bigquery_datasets" {
  source   = "./bigquery_datasets"
  for_each = { for ds in local.datasets : ds.id => ds }

  project_id                     = var.project_id
  project_number                 = data.google_project.current.number
  dataset_id                     = each.value.id
  friendly_name                  = each.value.friendly_name
  description                    = each.value.description
  location                       = var.region
  labels                         = each.value.labels
  access_rules                   = each.value.access_rules
  airflow_service_account_email  = module.airflow.airflow_service_account_email
  
  depends_on = [module.airflow]
}

module "bigquery_tables" {
  source = "./bigquery_tables"

  project_id   = var.project_id
  dataset_ids  = local.dataset_outputs
  depends_on   = [module.bigquery_datasets]
}

module "transfer_jobs" {
  source   = "./transfer_jobs"
  for_each = local.transfer_jobs

  project_id                     = var.project_id
  aws_access_key                 = var.aws_access_key
  aws_secret_key                 = var.aws_secret_key
  s3_bucket                      = var.s3_bucket
  transfer_job_display_name      = each.value.display_name
  destination_table_name         = each.value.destination_table
  data_path_uri                  = each.value.data_path
  destination_dataset_id         = local.dataset_outputs[each.value.destination_dataset]
  transfer_service_account_email = google_service_account.transfer_sa.email

  depends_on = [
    module.bigquery_datasets,
    module.bigquery_tables,
    google_project_iam_member.transfer_sa_roles,
    google_secret_manager_secret_version.aws_credentials_version,
    google_project_service.enable_transfer
  ]
}
