locals {
  # Update the file pattern to be more specific
  table_files = fileset(path.module, "**/*.yaml")
  table_configs = {
    for file in local.table_files : basename(file) => yamldecode(file("${path.module}/${file}"))
  }
  
  # Map dataset variable names to their values
  dataset_ids = {
    "data_sharing_dataset_id" = var.data_sharing_dataset_id
    "analytics_dataset_id"    = var.analytics_dataset_id
    "brone_zone_id"   = var.brone_zone_id
  }
}

# Add output for debugging
output "found_table_files" {
  value = local.table_files
  description = "List of table YAML files found"
}

output "table_configs" {
  value = local.table_configs
  description = "Parsed table configurations"
}

resource "google_bigquery_table" "tables" {
  for_each = local.table_configs

  dataset_id = local.dataset_ids[each.value.dataset_id_var_name]
  table_id   = each.value.table_id
  project    = var.project_id
  description = each.value.description

  labels = each.value.labels

  dynamic "time_partitioning" {
    for_each = lookup(each.value, "time_partitioning", []) != null ? [each.value.time_partitioning] : []
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
      mode        = field.mode
      description = field.description
    }
  ])
} 