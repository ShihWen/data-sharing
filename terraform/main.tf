# resource "google_storage_bucket" "my-bucket" {
#   name                     = "test-githubdemo-bucket-004" # You can change the bucket name
#   project                  = "open-data-v2-cicd" # REPLACE with your GCP Project ID, or use variable
#   location                 = "ASIA-EAST1" # You can change the location/region

#   force_destroy            = true
#   public_access_prevention = "enforced"
# }


# Configure the GCP Provider
provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

resource "google_storage_bucket" "my-bucket" {
  name                     = var.bucket_name
  project                  = var.gcp_project_id
  location                 = var.gcp_region
  force_destroy            = true
  public_access_prevention = "enforced"
}

# Include the BigQuery datasets module
module "bigquery_datasets" {
  source = "./bigquery_datasets"

  gcp_project_id = var.gcp_project_id
  gcp_region     = var.gcp_region
  deployment_env = var.deployment_env
  _dynamic_dataset_ids = var._dynamic_dataset_ids
}

# Include the BigQuery tables module
module "bigquery_tables" {
  source = "./bigquery_tables"

  gcp_project_id = var.gcp_project_id
  deployment_env = var.deployment_env
  _dynamic_dataset_ids = var._dynamic_dataset_ids

  depends_on = [
    module.bigquery_datasets
  ]
}
