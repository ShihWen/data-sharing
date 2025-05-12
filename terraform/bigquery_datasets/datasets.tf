locals {
  # Read and parse the datasets configuration file
  datasets_config = yamldecode(file("${path.module}/configs/datasets.yaml"))

  # Create a map of dataset configurations
  dataset_configs = {
    for dataset in local.datasets_config.datasets : dataset.dataset_id_var_name => dataset
  }
}

# Create BigQuery datasets
resource "google_bigquery_dataset" "datasets" {
  for_each = local.dataset_configs

  project    = var.gcp_project_id
  dataset_id = var._dynamic_dataset_ids[each.key]
  location   = var.gcp_region

  friendly_name = each.value.friendly_name
  description   = each.value.description

  labels = merge(
    each.value.labels,
    {
      env = var.deployment_env
    }
  )

  # Optional: Add more dataset configurations as needed
  # delete_contents_on_destroy = var.deployment_env != "prod"
  # default_partition_expiration_ms = 5184000000 # 60 days
  # default_table_expiration_ms = 5184000000 # 60 days
} 