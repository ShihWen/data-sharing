variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The GCP region"
  type        = string
  default     = "asia-east1"
}

variable "zone" {
  description = "The GCP zone"
  type        = string
  default     = "asia-east1-b"
}

variable "environment" {
  description = "Environment name (e.g., dev, prod)"
  type        = string
  default     = "dev"
}

variable "airflow_sa_name" {
  description = "Name for the Airflow service account"
  type        = string
  default     = "airflow-service-account"
}

variable "airflow_storage_class" {
  description = "Storage class for Airflow GCS bucket"
  type        = string
  default     = "STANDARD"
}

variable "dataset_ids" {
  description = "Map of dataset IDs to their BigQuery dataset IDs"
  type        = map(string)
  default     = {}
} 
