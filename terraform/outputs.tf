output "dataset_ids" {
  description = "Map of created dataset IDs"
  value = {
    for k, v in module.bigquery_datasets : k => v.dataset_id
  }
}

output "dataset_urls" {
  description = "Map of dataset URLs in BigQuery console"
  value = {
    for k, v in module.bigquery_datasets : k => v.dataset_url
  }
}

output "dataset_locations" {
  description = "Map of dataset locations"
  value = {
    for k, v in module.bigquery_datasets : k => v.dataset_location
  }
}

output "mrt_datasets" {
  description = "Information about MRT datasets"
  value = {
    bronze = module.bigquery_datasets["tpe_mrt_bronze"].dataset_id
    silver = module.bigquery_datasets["tpe_mrt_silver"].dataset_id
    gold   = module.bigquery_datasets["tpe_mrt_gold"].dataset_id
  }
} 