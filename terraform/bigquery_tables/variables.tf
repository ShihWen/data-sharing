variable "gcp_project_id" {
  description = "The ID of the GCP project to deploy resources into."
  type        = string
}

variable "deployment_env" {
  description = "The deployment environment (e.g., dev, prod). To be used for tagging etc."
  type        = string
}

variable "_dynamic_dataset_ids" {
  description = "A map to allow dynamic lookup of dataset ID variables."
  type        = map(string)
  default     = {} # Jenkins will override this
} 