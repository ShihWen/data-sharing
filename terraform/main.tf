# resource "google_storage_bucket" "my-bucket" {
#   name                     = "test-githubdemo-bucket-004" # You can change the bucket name
#   project                  = "open-data-v2-cicd" # REPLACE with your GCP Project ID, or use variable
#   location                 = "ASIA-EAST1" # You can change the location/region

#   force_destroy            = true
#   public_access_prevention = "enforced"
# }


# Configure the GCP Provider (optional, but recommended)
provider "google" {
  project = var.gcp_project_id # Use the project variable
  region  = var.gcp_region     # Use the region variable
}

resource "google_storage_bucket" "my-bucket" {
  name                     = var.bucket_name # Use the bucket name variable
  project                  = var.gcp_project_id # Use the project variable
  location                 = var.gcp_region     # Use the region variable

  force_destroy            = true
  public_access_prevention = "enforced"

  # Add other resource configurations here, using variables as needed
}

resource "google_bigquery_dataset" "test_dataset" {
  dataset_id                  = "test_dataset"
  project                     = var.gcp_project_id
  location                    = var.gcp_region
  delete_contents_on_destroy = true
  labels = {
    environment = "dev"
  }
}
