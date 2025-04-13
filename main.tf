resource "google_storage_bucket" "my-bucket" {
  name                     = "test-githubdemo-bucket-002" # You can change the bucket name
  project                  = "open-data-v2-cicd" # REPLACE with your GCP Project ID, or use variable
  location                 = "ASIA-EAST1" # You can change the location/region

  force_destroy            = true
  public_access_prevention = "enforced"
}
