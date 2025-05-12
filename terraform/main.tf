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

# Create BigQuery datasets
resource "google_bigquery_dataset" "my_dataset_sales" {
  dataset_id    = var.sales_dataset_id
  friendly_name = "Sales Data"
  description   = "Dataset for sales related information"
  location      = var.gcp_region
  project       = var.gcp_project_id

  labels = {
    env                        = var.deployment_env
    team                       = "analytics"
    goog-terraform-provisioned = "true"
  }
}

resource "google_bigquery_dataset" "my_dataset_marketing" {
  dataset_id    = var.marketing_dataset_id
  friendly_name = "Marketing Data"
  description   = "Dataset for marketing campaigns and leads"
  location      = var.gcp_region
  project       = var.gcp_project_id

  labels = {
    env                        = var.deployment_env
    team                       = "marketing"
    goog-terraform-provisioned = "true"
  }
}

# Include the BigQuery tables module
module "bigquery_tables" {
  source = "./bigquery_tables"

  # Pass through required variables
  gcp_project_id = var.gcp_project_id
  deployment_env = var.deployment_env
  _dynamic_dataset_ids = var._dynamic_dataset_ids
}
