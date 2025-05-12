terraform {
  backend "gcs" {
    # Bucket name and service account are environment-specific, so we'll pass them via -backend-config in Jenkinsfile
    # bucket = var.terraform_state_bucket_name # THIS IS NOT ALLOWED IN BACKEND BLOCK
    # storage_account will also be passed via -backend-config

    prefix = "terraform/state" # Shared path inside the bucket
    region = "asia-east1" # Set region here if it's the same for all environments
  }
}
