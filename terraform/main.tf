provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  datasets = yamldecode(file("${path.module}/config/datasets.yaml")).datasets
}

module "bigquery_datasets" {
  source   = "./bigquery_datasets"
  for_each = { for ds in local.datasets : ds.id => ds }

  project_id    = var.project_id
  dataset_id    = each.value.id
  friendly_name = each.value.friendly_name
  description   = each.value.description
  location      = var.region
  labels        = each.value.labels

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
  data_sharing_dataset_id   = module.bigquery_datasets["data_sharing_dataset"].dataset_id
  analytics_dataset_id      = module.bigquery_datasets["analytics_dataset"].dataset_id
  tpe_mrt_bronze_dataset_id = module.bigquery_datasets["tpe_mrt_bronze"].dataset_id
  tpe_mrt_silver_dataset_id = module.bigquery_datasets["tpe_mrt_silver"].dataset_id
  tpe_mrt_gold_dataset_id   = module.bigquery_datasets["tpe_mrt_gold"].dataset_id
  depends_on                = [module.bigquery_datasets]
}
