# prod.tfvars

gcp_project_id          = "open-data-v2-cicd-prod" # Your PROD GCP Project ID
terraform_state_bucket_name = "terraform-state-bucket-project-data-sharing-prod" # Your PROD GCS bucket for Terraform state
deployment_env = "prod"

# Dynamic dataset IDs mapping
_dynamic_dataset_ids = {
  sales_dataset_id     = "sales_data"
  marketing_dataset_id = "marketing_data"
}

# Add values for other variables used in main.tf if needed
# bucket_name = "test-githubdemo-bucket-prod-001" # Optional: specify a different name for prod
# instance_type = "e2-standard-2"