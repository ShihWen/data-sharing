output "airflow_vm_name" {
  description = "The name of the Airflow VM instance"
  value       = google_compute_instance.airflow.name
}

output "airflow_vm_ip" {
  description = "The external IP of the Airflow VM"
  value       = google_compute_instance.airflow.network_interface[0].access_config[0].nat_ip
}

output "airflow_bucket_name" {
  description = "The name of the GCS bucket for Airflow"
  value       = google_storage_bucket.airflow_bucket.name
}

output "airflow_webserver_url" {
  description = "The URL of the Airflow webserver"
  value       = "http://${google_compute_instance.airflow.network_interface[0].access_config[0].nat_ip}:8081"
}

output "scheduler_service_account" {
  description = "The email of the service account used for scheduling"
  value       = google_service_account.scheduler_sa.email
}

output "start_scheduler_job" {
  description = "The name of the Cloud Scheduler job that starts the Airflow VM"
  value       = google_cloud_scheduler_job.start_airflow.name
}

output "stop_scheduler_job" {
  description = "The name of the Cloud Scheduler job that stops the Airflow VM"
  value       = google_cloud_scheduler_job.stop_airflow.name
}

output "operating_schedule" {
  description = "The operating schedule of the Airflow instance"
  value       = "Runs from Saturday 8:00 AM to Sunday 00:00 AM (Taiwan Time)"
} 