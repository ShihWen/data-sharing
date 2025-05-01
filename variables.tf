variable "gcp_project_id" {
  description = "The ID of the GCP project to deploy resources into."
  type        = string
}

variable "gcp_region" {
  description = "The GCP region to deploy resources into."
  type        = string
  default     = "asia-east1" # Set a default if it's often the same
}

variable "terraform_state_bucket_name" {
  description = "The name of the GCS bucket for storing Terraform state."
  type        = string
}

variable "bucket_name" {
  description = "The name for the example GCS bucket created by main.tf."
  type        = string
  default     = "test-githubdemo-bucket-001" # Example default name
}
