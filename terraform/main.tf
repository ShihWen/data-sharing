terraform {
  required_version = ">= 1.11.3"
}

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

resource "google_project_service" "enable_cloudbuild" {
  project            = var.project_id
  service            = "cloudbuild.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "enable_cloudrun" {
  project            = var.project_id
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "enable_cloudfunctions" {
  project            = var.project_id
  service            = "cloudfunctions.googleapis.com"
  disable_on_destroy = false
}

# A dedicated bucket for storing data lake files.
resource "google_storage_bucket" "data_lake" {
  name          = var.gcs_data_lake_bucket
  location      = var.region
  project       = var.project_id
  force_destroy = false # Set to true only in non-prod environments if you want to delete non-empty buckets
  uniform_bucket_level_access = true
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
      schedule            = "every saturday 00:30"
    }
    # mrt_station = {
    #   display_name        = "MRT Station Data Transfer"
    #   destination_table   = "mrt_station"
    #   data_path           = "s3://${var.s3_bucket}/mrt-station/mrt_station*"
    #   destination_dataset = "tpe_mrt_bronze"
    #   schedule            = "every saturday 01:00"
    # }
    mrt_exit = {
      display_name        = "MRT Exit Data Transfer"
      destination_table   = "mrt_exit"
      data_path           = "s3://${var.s3_bucket}/mrt-station/mrt_exit*"
      destination_dataset = "tpe_mrt_bronze"
      schedule            = "every saturday 01:30"
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

# Secrets for the TDX API
resource "google_secret_manager_secret" "tdx_client_id" {
  secret_id = "tdx_client_id"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "tdx_client_id_version" {
  secret      = google_secret_manager_secret.tdx_client_id.id
  secret_data = var.tdx_client_id
}

resource "google_secret_manager_secret" "tdx_client_secret" {
  secret_id = "tdx_client_secret"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "tdx_client_secret_version" {
  secret      = google_secret_manager_secret.tdx_client_secret.id
  secret_data = var.tdx_client_secret
}

# Grant the Airflow SA permission to invoke Cloud Functions.
# This is required for the CloudFunctionInvokeFunctionOperator, which uses the
# 'cloudfunctions.functions.call' permission, found in the developer role.
resource "google_project_iam_member" "airflow_sa_cloudfunctions_invoker" {
  project = var.project_id
  role    = "roles/cloudfunctions.developer"
  member  = "serviceAccount:${module.airflow.airflow_service_account_email}"
}

# Grant the Airflow SA permission to invoke the Cloud Function.
resource "google_cloud_run_service_iam_member" "airflow_invokes_mrt_station_ntmc" {
  location = module.mrt_station_ntmc_function.function_location
  project  = module.mrt_station_ntmc_function.function_project
  service  = module.mrt_station_ntmc_function.function_name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${module.airflow.airflow_service_account_email}"
}

module "airflow" {
  source = "./airflow"

  project_id   = var.project_id
  region       = var.region
  zone         = var.zone
  mrt_station_ntmc_function_uri = module.mrt_station_ntmc_function.function_uri
  depends_on = [
    google_project_service.enable_secretmanager,
    google_secret_manager_secret_version.tdx_client_id_version,
    google_secret_manager_secret_version.tdx_client_secret_version
  ]
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
  schedule                       = each.value.schedule

  depends_on = [
    module.bigquery_datasets,
    module.bigquery_tables,
    google_project_iam_member.transfer_sa_roles,
    google_secret_manager_secret_version.aws_credentials_version,
    google_project_service.enable_transfer
  ]
}

module "mrt_station_ntmc_function" {
  source = "./cloud_function"

  project_id                  = var.project_id
  region                      = var.region
  function_name               = "mrt-station-ntmc-fetcher"
  source_dir                  = "${path.module}/../gcp/cloud_functions/mrt_station_ntmc"
  entry_point                 = "main"

  environment_variables = {
    GCP_PROJECT   = var.project_id
    GCS_BUCKET    = var.gcs_data_lake_bucket
    TDX_AUTH_URL  = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
  }

  depends_on = [
    google_project_service.enable_cloudbuild,
    google_project_service.enable_cloudrun,
    google_project_service.enable_cloudfunctions,
    google_storage_bucket.data_lake
  ]
}
