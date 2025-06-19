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

variable "schedule" {
  description = "Schedule for the transfer job (in UTC). Format: 'every DAYOFWEEK HH:MM' or 'every N hours' or 'every day HH:MM'"
  type        = string
  default     = "every saturday 00:30"  # Runs at 00:30 UTC every Saturday
}

variable "transfer_job_display_name" {
  description = "Display name for the BigQuery transfer job."
  type        = string
}

variable "destination_table_name" {
  description = "The destination table name template."
  type        = string
}

variable "data_path_uri" {
  description = "The S3 data path URI."
  type        = string
}

variable "destination_dataset_id" {
  description = "The destination BigQuery dataset ID."
  type        = string
}

variable "transfer_service_account_email" {
  description = "The email of the service account to be used for the transfer."
  type        = string
} 