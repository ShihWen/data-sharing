# terraform/bigquery_tables/tables.tf

locals {
  _debug_current_path_module = path.module # Should be ./bigquery_tables when run from terraform/
  _debug_schemas_dir_to_scan = "${path.module}/schemas" # e.g., ./bigquery_tables/schemas

  # Find all .yaml files in the schemas directory and its subdirectories
  table_schema_files = fileset("${path.module}/schemas", "**/*.yaml")

  # Create a map of table configurations from the YAML files
  # The key for the map will be the file path (unique identifier)
  # The value will be the parsed YAML content
  table_configs = {
    for fpath in local.table_schema_files :
    # fpath => yamldecode(file("${path.module}/schemas/${fpath}"))
    fpath => yamldecode(file("${local._debug_schemas_dir_to_scan}/${fpath}")) # Use the debugged path here too
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

# For temp testing
output "debug_BQT_actual_path_module_in_tables_tf" {
  value = local._debug_current_path_module
}
output "debug_BQT_schemas_directory_scanned_by_fileset" {
  value = local._debug_schemas_dir_to_scan
}
output "debug_BQT_table_schema_files_FOUND" { # Renamed for clarity
  value = local.table_schema_files
}
output "debug_BQT_table_configs_PARSED" { # Renamed for clarity
  value     = local.table_configs
  sensitive = true
}
output "debug_BQT_dynamic_dataset_ids_var" {
  value = var._dynamic_dataset_ids
}
