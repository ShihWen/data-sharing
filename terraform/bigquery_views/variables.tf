variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "dataset_ids" {
  description = "Map of dataset IDs to their BigQuery dataset IDs"
  type        = map(string)
} 