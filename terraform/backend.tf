terraform {
  backend "gcs" {
    prefix = "terraform/state"
    region = "asia-east1"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
} 