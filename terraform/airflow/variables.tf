variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "asia-east1"
}

variable "zone" {
  description = "GCP zone"
  type        = string
  default     = "asia-east1-a"
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