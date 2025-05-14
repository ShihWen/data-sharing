output "dataset_ids" {
  description = "Map of created dataset IDs"
  value = {
    for k, v in module.bigquery_datasets : k => v.dataset_id
  }
}

output "dataset_urls" {
  description = "Map of created dataset URLs"
  value = {
    for k, v in module.bigquery_datasets : k => v.dataset_url
  }
} 