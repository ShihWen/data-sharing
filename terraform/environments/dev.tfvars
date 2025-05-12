# dev.tfvars

gcp_project_id          = "open-data-v2-cicd" # Your DEV GCP Project ID
terraform_state_bucket_name = "terraform-state-bucket-project-data-sharing" # Your DEV GCS bucket for Terraform state

# Add values for other variables used in main.tf if needed
# bucket_name = "test-githubdemo-bucket-dev-001" # Optional: specify a different name for dev

deployment_env = "dev"

# Map of variable names to actual dataset IDs
# The keys here must match the dataset_id_var_name values in your schema YAML files
_dynamic_dataset_ids = {
  sales_dataset_id     = "sales_data_dev"      # Matches dataset_id_var_name in orders.yaml
  marketing_dataset_id = "marketing_data_dev"   # For marketing tables
}