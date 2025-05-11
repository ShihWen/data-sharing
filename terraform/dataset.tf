# terraform/datasets.tf

resource "google_bigquery_dataset" "my_dataset_sales" {
  project    = var.gcp_project_id
  dataset_id = var.sales_dataset_id # Define this variable in variables.tf and set in .tfvars
  friendly_name = "Sales Data"
  description   = "Dataset for sales related information"
  location      = var.gcp_region     # Or a specific location for this dataset
  labels = {
    env       = var.deployment_env # e.g., "dev" or "prod", passed from Jenkins or tfvars
    team      = "analytics"
  }
}

resource "google_bigquery_dataset" "my_dataset_marketing" {
  project    = var.gcp_project_id
  dataset_id = var.marketing_dataset_id # Define this variable
  friendly_name = "Marketing Data"
  description   = "Dataset for marketing campaigns and leads"
  location      = var.gcp_region
  labels = {
    env       = var.deployment_env
    team      = "marketing"
  }
}

# Add more dataset definitions here as needed