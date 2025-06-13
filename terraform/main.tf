provider "google" {
  project = var.project_id
  region  = var.region
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
}

module "airflow" {
  source = "./airflow"

  project_id   = var.project_id
  region       = var.region
  zone         = var.zone
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
  source = "./transfer_jobs"

  project_id     = var.project_id
  aws_access_key = var.aws_access_key
  aws_secret_key = var.aws_secret_key
  s3_bucket      = var.s3_bucket
  dataset_ids    = local.dataset_outputs
  depends_on     = [module.bigquery_datasets, module.bigquery_tables]
}
