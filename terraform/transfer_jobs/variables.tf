variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "aws_access_key" {
  description = "AWS access key for S3 access"
  type        = string
}

variable "aws_secret_key" {
  description = "AWS secret key for S3 access"
  type        = string
}

variable "s3_bucket" {
  description = "AWS S3 bucket name containing the MRT data"
  type        = string
}

variable "bronze_dataset_id" {
  description = "The ID of the BigQuery bronze dataset"
  type        = string
}

variable "schedule" {
  description = "Schedule for the transfer job in cron format"
  type        = string
  default     = "0 0 * * 0"  # Weekly on Sunday at midnight
} 