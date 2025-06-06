locals {
  # Update the file pattern to be more specific
  table_files = fileset(path.module, "**/*.yaml")
  table_configs = {
    for file in local.table_files : basename(file) => yamldecode(file("${path.module}/${file}"))
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
      name = field.name
      type = field.type
      mode = field.mode
      # Only include description if it exists and is not empty
      description = lookup(field, "description", "")
    }
  ])
} 