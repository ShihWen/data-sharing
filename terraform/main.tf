provider "google" {
  project = var.project_id
  region  = var.region
}

# Example dataset for data sharing
module "sharing_dataset" {
  source = "./bigquery_datasets"

  project_id  = var.project_id
  dataset_id  = "data_sharing_dataset"
  friendly_name = "Data Sharing Dataset"
  description  = "Dataset for sharing data between different parties"
  location     = var.region

  labels = {
    environment = "development"
    purpose     = "data_sharing"
  }

  access_rules = [
    {
      role          = "OWNER"
      special_group = "projectOwners"
    },
    {
      role          = "READER"
      special_group = "projectReaders"
    },
    {
      role          = "WRITER"
      special_group = "projectWriters"
    }
  ]
}

# Just a test resource to verify our setup
resource "google_storage_bucket" "test_bucket" {
  name          = "test-bucket-${var.project_id}"
  location      = var.region
  force_destroy = true
} 