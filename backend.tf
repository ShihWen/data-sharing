terraform {
  backend "gcs" {
    bucket = "terraform-state-bucket-project-data-sharing"  # REPLACE with your GCS bucket name
    prefix = "terraform/state"                       # Optional: path inside the bucket for state files
    region = "asia-east1"                             # REPLACE with your bucket's region
    # Optional - Explicitly specify the service account email (recommended for clarity)
    # service_account_email = "jenkins-cicd-dev@open-data-v2-cicd.iam.gserviceaccount.com" # REPLACE with your SA email
  }
}