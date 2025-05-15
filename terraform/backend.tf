terraform {
  backend "gcs" {
    bucket = "terraform-state-data-sharing-dev-new"
    prefix = "terraform/state"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
} 