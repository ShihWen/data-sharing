output "dataset_id" {
  description = "The ID of the created dataset"
  value       = google_bigquery_dataset.main.dataset_id
}

output "dataset_url" {
  description = "The full URL of the created dataset"
  value       = google_bigquery_dataset.main.self_link
}

output "dataset_location" {
  description = "The location of the created dataset"
  value       = google_bigquery_dataset.main.location
} 