terraform {
  backend "gcs" {
    bucket = "terraform-state-bucket-project-data-sharing"  # your bucket name
    prefix = "terraform/state"                       # path inside the bucket
    region = "asia-east1"  // <--- Region is defined HERE in backend.tf
  }
}

resource "google_storage_bucket" "my-bucket" {
  name                     = "test-githubdemo-bucket-001"
  project                  = "open-data-v2-cicd"
  location                 = "asia-east1"
  force_destroy            = true
  public_access_prevention = "enforced"
}
