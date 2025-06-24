variable "project_id" {
  description = "The GCP project ID."
  type        = string
}

variable "region" {
  description = "The GCP region for the Cloud Function."
  type        = string
}

variable "function_name" {
  description = "The name of the Cloud Function."
  type        = string
}

variable "source_dir" {
  description = "The path to the directory containing the Cloud Function source code."
  type        = string
}

variable "entry_point" {
  description = "The name of the function in the source code to be executed."
  type        = string
}

variable "environment_variables" {
  description = "A map of environment variables to pass to the Cloud Function."
  type        = map(string)
  default     = {}
}

variable "invoker_service_account_email" {
  description = "The service account email that will be granted invoker permissions."
  type        = string
} 