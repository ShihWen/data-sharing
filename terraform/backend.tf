terraform {
  backend "gcs" {
    bucket = "terraform-state-data-sharing-dev-new"
    prefix = "terraform/state"
  }
} 