variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The GCP region for resources"
  type        = string
  default     = "asia-east1"
} 

variable "aws_access_key" {
  description = "AWS access key for S3 access"
  type        = string
  sensitive   = true
}

variable "aws_secret_key" {
  description = "AWS secret key for S3 access"
  type        = string
  sensitive   = true
}

variable "s3_bucket" {
  description = "AWS S3 bucket name containing the MRT data"
  type        = string
} 