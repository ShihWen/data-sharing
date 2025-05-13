terraform {
  backend "gcs" {
    # Bucket name is environment-specific, so we'll pass it via -backend-config in Jenkinsfile
    # bucket = var.terraform_state_bucket_name # THIS IS NOT ALLOWED IN BACKEND BLOCK
    
    prefix = "terraform/state" # Shared path inside the bucket
    region = "asia-east1" # Set region here if it's the same for all environments
    access_token = "" # Will be populated via environment variable
  }
}
