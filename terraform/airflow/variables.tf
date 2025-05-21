variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "asia-east1"
}

variable "zone" {
  description = "GCP zone"
  type        = string
  default     = "asia-east1-a"
} 