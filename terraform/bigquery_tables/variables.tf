variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "dataset_ids" {
  description = "Map of dataset IDs to their BigQuery dataset IDs"
  type        = map(string)
}

# Keep the existing dataset ID variables for backward compatibility
# variable "tpe_mrt_bronze_dataset_id" {
#   description = "The ID of the TPE MRT Bronze dataset"
#   type        = string
#   default     = null
# }

# variable "tpe_mrt_silver_dataset_id" {
#   description = "The ID of the TPE MRT Silver dataset"
#   type        = string
#   default     = null
# }

# variable "tpe_mrt_gold_dataset_id" {
#   description = "The ID of the TPE MRT Gold dataset"
#   type        = string
#   default     = null
# }
