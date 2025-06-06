variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "aws_access_key" {
  description = "AWS access key for S3 bucket access"
  type        = string
}

variable "aws_secret_key" {
  description = "AWS secret key for S3 bucket access"
  type        = string
}

variable "s3_bucket" {
  description = "S3 bucket name containing the data"
  type        = string
}

variable "dataset_ids" {
  description = "Map of dataset IDs to their BigQuery dataset IDs"
  type        = map(string)
}

variable "schedule" {
  description = "Schedule for the transfer job (in UTC). Format: 'every DAYOFWEEK HH:MM' or 'every N hours' or 'every day HH:MM'"
  type        = string
  default     = "every saturday 00:30"  # Runs at 00:30 UTC every Saturday
} 