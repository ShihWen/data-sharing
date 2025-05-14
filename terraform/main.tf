provider "google" {
  project = var.project_id
  region  = var.region
}

# Just a test resource to verify our setup
resource "google_storage_bucket" "test_bucket" {
  name          = "test-bucket-${var.project_id}"
  location      = var.region
  force_destroy = true
} 