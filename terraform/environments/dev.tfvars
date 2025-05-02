# dev.tfvars

gcp_project_id          = "open-data-v2-cicd" # Your DEV GCP Project ID
terraform_state_bucket_name = "terraform-state-bucket-project-data-sharing" # Your DEV GCS bucket for Terraform state

# Add values for other variables used in main.tf if needed
# bucket_name = "test-githubdemo-bucket-dev-001" # Optional: specify a different name for dev
# instance_type = "e2-medium"