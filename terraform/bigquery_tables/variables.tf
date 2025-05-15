 variable "project_id" {
  description = "The ID of the project where tables will be created"
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
  description = "The ID of the Taipei MRT bronze dataset"
  type        = string
}

variable "tpe_mrt_silver_dataset_id" {
  description = "The ID of the Taipei MRT silver dataset"
  type        = string
}

variable "tpe_mrt_gold_dataset_id" {
  description = "The ID of the Taipei MRT gold dataset"
  type        = string
}
