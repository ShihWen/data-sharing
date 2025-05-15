variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "data_sharing_dataset_id" {
  description = "The ID of the data sharing dataset"
  type        = string
}

variable "analytics_dataset_id" {
  description = "The ID of the analytics dataset"
  type        = string
}

variable "tpe_mrt_bronze_dataset_id" {
  description = "The ID of the TPE MRT bronze dataset"
  type        = string
}

variable "tpe_mrt_silver_dataset_id" {
  description = "The ID of the TPE MRT silver dataset"
  type        = string
}

variable "tpe_mrt_gold_dataset_id" {
  description = "The ID of the TPE MRT gold dataset"
  type        = string
}
