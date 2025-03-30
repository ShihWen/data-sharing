resource "google_storage_bucket" "my-bucket" {
  name                     = "test-githubdemo-bucket-001"
  project                  = "open-data-v2-cicd"
  location                 = "asia-east1"
  force_destroy            = true
  public_access_prevention = "enforced"
}
