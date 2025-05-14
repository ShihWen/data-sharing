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

# Just a test resource to verify our setup
resource "google_storage_bucket" "test_bucket" {
  name          = "test-bucket-${var.project_id}"
  location      = var.region
  force_destroy = true
} 