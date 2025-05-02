terraform {
  backend "gcs" {
    # Bucket name is environment-specific, so we'll pass it via -backend-config in Jenkinsfile
    # bucket = var.terraform_state_bucket_name # THIS IS NOT ALLOWED IN BACKEND BLOCK

    prefix = "terraform/state" # Shared path inside the bucket
    region = "asia-east1" # Set region here if it's the same for all environments

    # service_account_email = "jenkins-cicd-dev@open-data-v2-cicd.iam.gserviceaccount.com" # Optional, can be set here or picked up from GCLOUD_AUTH_ACTIVATED
  }
}
