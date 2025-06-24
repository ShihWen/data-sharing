variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The GCP region for resources"
  type        = string
  default     = "asia-east1"
}

variable "zone" {
  description = "The GCP zone for VM instances"
  type        = string
  default     = "asia-east1-b"
}

variable "aws_access_key" {
  description = "The AWS access key for S3."
  type        = string
  sensitive   = true
}

variable "aws_secret_key" {
  description = "The AWS secret key for S3."
  type        = string
  sensitive   = true
}

variable "tdx_client_id" {
  description = "The client ID for the TDX API."
  type        = string
  sensitive   = true
}

variable "tdx_client_secret" {
  description = "The client secret for the TDX API."
  type        = string
  sensitive   = true
}

variable "s3_bucket" {
  description = "AWS S3 bucket name containing the MRT data"
  type        = string
} 