output "mrt_traffic_transfer_name" {
  description = "The resource name of the transfer config for MRT traffic data"
  value       = google_bigquery_data_transfer_config.mrt_traffic_transfer.name
}

output "mrt_station_transfer_name" {
  description = "The resource name of the transfer config for MRT station data"
  value       = google_bigquery_data_transfer_config.mrt_station_transfer.name
}

output "mrt_exit_transfer_name" {
  description = "The resource name of the transfer config for MRT exit data"
  value       = google_bigquery_data_transfer_config.mrt_exit_transfer.name
}

output "aws_credentials_secret_name" {
  description = "The name of the Secret Manager secret storing AWS credentials"
  value       = google_secret_manager_secret.aws_credentials.name
  sensitive   = true
} 