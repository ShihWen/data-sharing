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

  project_id  = var.project_id
  dataset_id  = each.value.id
  friendly_name = each.value.friendly_name
  description  = each.value.description
  location     = var.region

  labels = each.value.labels
  access_rules = each.value.access_rules
}

module "bigquery_tables" {
  source = "./bigquery_tables"
  
  project_id = var.project_id
  data_sharing_dataset_id = module.bigquery_datasets["data_sharing_dataset"].dataset_id
  analytics_dataset_id = module.bigquery_datasets["analytics_dataset"].dataset_id
  brone_zone_id = module.bigquery_datasets["brone_zone"].dataset_id
  depends_on = [module.bigquery_datasets]
} 