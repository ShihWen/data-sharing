# terraform/bigquery_tables/tables.tf

locals {
  # Find all .yaml files in the schemas directory and its subdirectories
  table_schema_files = fileset("${path.module}/schemas", "**/*.yaml")

  # Create a map of table configurations from the YAML files
  # The key for the map will be the file path (unique identifier)
  # The value will be the parsed YAML content
  table_configs = {
    for fpath in local.table_schema_files :
    fpath => yamldecode(file("${path.module}/schemas/${fpath}"))
  }
}

resource "google_bigquery_table" "this" {
  for_each = local.table_configs

  project     = var.gcp_project_id
  # Dynamically get the dataset_id based on the variable name specified in YAML
  # This requires that the variable (e.g., var.sales_dataset_id) is correctly defined
  # and its value is available (e.g., from your .tfvars files).
  dataset_id  = var._dynamic_dataset_ids[each.value.dataset_id_var_name]
  table_id    = each.value.table_id
  description = try(each.value.description, null) # Optional: use try for safety
  labels      = try(each.value.labels, {})        # Optional

  # The schema argument expects a JSON string.
  # The `yamldecode` function parses YAML into Terraform data structures.
  # `jsonencode` converts these Terraform structures into a JSON string.
  schema = jsonencode(each.value.schema)

  # Optional: Add support for clustering, partitioning, etc., from YAML
  dynamic "time_partitioning" {
    for_each = try(each.value.time_partitioning, null) != null ? [each.value.time_partitioning] : []
    content {
      type  = time_partitioning.value.type
      field = try(time_partitioning.value.field, null)
      # expiration_ms = try(time_partitioning.value.expiration_ms, null) # etc.
    }
  }

  clustering = try(each.value.clustering, null)

  deletion_protection = false # Set to true for production tables you don't want accidentally deleted
  
  # This depends_on block ensures datasets are created before tables referencing them.
  # It's a bit broad, but safer. You could make it more specific if you parse dataset IDs
  # from YAML keys earlier and map them directly to google_bigquery_dataset resources.
  depends_on = [
    google_bigquery_dataset.my_dataset_sales,
    google_bigquery_dataset.my_dataset_marketing
    # Add all other dataset resources defined in datasets.tf here
  ]
}