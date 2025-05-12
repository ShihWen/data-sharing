# No module-specific variables needed for now
# All variables are passed from the root module 

variable "gcp_project_id" {
  description = "The ID of the GCP project to deploy resources into."
  type        = string
}

variable "gcp_region" {
  description = "The GCP region to deploy resources into."
  type        = string
}

variable "deployment_env" {
  description = "The deployment environment (e.g., dev, prod)."
  type        = string
}

variable "_dynamic_dataset_ids" {
  description = "A map to allow dynamic lookup of dataset ID variables."
  type        = map(string)
} 