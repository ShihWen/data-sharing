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

//
variable "sales_dataset_id" {
  description = "The ID for the sales BigQuery dataset."
  type        = string
}

variable "marketing_dataset_id" {
  description = "The ID for the marketing BigQuery dataset."
  type        = string
}

variable "deployment_env" {
  description = "The deployment environment (e.g., dev, prod). To be used for tagging etc."
  type        = string
  # This will be effectively set by your Jenkins pipeline's DEPLOYMENT_ENV
  # but you might want a default if running terraform locally.
  # default     = "dev"
}

# This is a helper variable to dynamically access other variables by name.
# It will be populated in your .tfvars files.
variable "_dynamic_dataset_ids" {
  description = "A map to allow dynamic lookup of dataset ID variables."
  type        = map(string)
  default     = {} # Jenkins will override this
}
