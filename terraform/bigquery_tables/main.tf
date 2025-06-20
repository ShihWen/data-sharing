locals {
  # Update the file pattern to be more specific
  table_files = fileset(path.module, "**/*.yaml")
  table_configs = {
    for file in local.table_files : trimsuffix(file, ".yaml") => yamldecode(file("${path.module}/${file}"))
  }
}

# Add output for debugging
output "found_table_files" {
  value       = local.table_files
  description = "List of table YAML files found"
}

output "table_configs" {
  value       = local.table_configs
  description = "Parsed table configurations"
}

resource "google_bigquery_table" "tables" {
  for_each = local.table_configs

  dataset_id  = var.dataset_ids[each.value.dataset_id_var_name]
  table_id    = each.value.table_id
  project     = var.project_id
  description = each.value.description

  labels = each.value.labels

  deletion_protection = false

  dynamic "time_partitioning" {
    for_each = contains(keys(each.value), "time_partitioning") ? [each.value.time_partitioning] : []
    content {
      type  = time_partitioning.value.type
      field = time_partitioning.value.field
    }
  }

  # Directly assign clustering if it exists
  clustering = lookup(each.value, "clustering", null)

  schema = jsonencode([
    for field in each.value.schema : {
      name        = field.name
      type        = field.type
      mode        = lookup(field, "mode", "NULLABLE") # Default to NULLABLE
      description = lookup(field, "description", "")
      # Handle nested fields for RECORD types
      fields = lookup(field, "fields", null) != null ? [
        for sub_field in field.fields : {
          name        = sub_field.name
          type        = sub_field.type
          mode        = lookup(sub_field, "mode", "NULLABLE")
          description = lookup(sub_field, "description", "")
        }
      ] : null
    }
  ])
} 