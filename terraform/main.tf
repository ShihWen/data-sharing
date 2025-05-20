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
}

module "bigquery_datasets" {
  source   = "./bigquery_datasets"
  for_each = { for ds in local.datasets : ds.id => ds }

  project_id      = var.project_id
  project_number  = data.google_project.current.number
  dataset_id      = each.value.id
  friendly_name   = each.value.friendly_name
  description     = each.value.description
  location        = var.region
  labels          = each.value.labels

  access_rules = [
    for rule in each.value.access_rules : {
      role                  = rule.role
      user_by_email         = lookup(rule, "user_by_email", null)
      group_by_email        = lookup(rule, "group_by_email", null)
      special_group         = lookup(rule, "special_group", null)
      service_account_email = lookup(rule, "service_account_email", null)
    }
  ]
}

module "bigquery_tables" {
  source = "./bigquery_tables"

  project_id                = var.project_id
  tpe_mrt_bronze_dataset_id = module.bigquery_datasets["tpe_mrt_bronze"].dataset_id
  tpe_mrt_silver_dataset_id = module.bigquery_datasets["tpe_mrt_silver"].dataset_id
  tpe_mrt_gold_dataset_id   = module.bigquery_datasets["tpe_mrt_gold"].dataset_id
  depends_on                = [module.bigquery_datasets]
}

module "transfer_jobs" {
  source = "./transfer_jobs"

  project_id        = var.project_id
  aws_access_key    = var.aws_access_key
  aws_secret_key    = var.aws_secret_key
  s3_bucket         = var.s3_bucket
  bronze_dataset_id = module.bigquery_datasets["tpe_mrt_bronze"].dataset_id
  depends_on        = [module.bigquery_datasets, module.bigquery_tables]
}
