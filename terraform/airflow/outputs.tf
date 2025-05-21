output "airflow_vm_ip" {
  description = "The IP address of the Airflow VM"
  value       = google_compute_instance.airflow.network_interface[0].access_config[0].nat_ip
}

output "airflow_vm_name" {
  description = "The name of the Airflow VM"
  value       = google_compute_instance.airflow.name
} 