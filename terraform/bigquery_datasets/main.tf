resource "google_bigquery_dataset" "main" {
  dataset_id                 = var.dataset_id
  friendly_name              = var.friendly_name
  description                = var.description
  location                   = var.location
  project                    = var.project_id
  delete_contents_on_destroy = var.delete_contents_on_destroy

  labels = var.labels

  dynamic "access" {
    for_each = var.access_rules
    content {
      role           = access.value.role
      user_by_email  = lookup(access.value, "user_by_email", null)
      group_by_email = lookup(access.value, "group_by_email", null)
      special_group  = lookup(access.value, "special_group", null)
    }
  }
} 