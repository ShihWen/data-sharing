output "function_uri" {
  description = "The URI of the deployed Cloud Function."
  value       = google_cloudfunctions2_function.function.service_config[0].uri
} 