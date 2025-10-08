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

  dataset_id  = dirname(each.key)
  table_id    = each.value.table_id
  project     = var.project_id
  description = each.value.description

  labels = lookup(each.value, "labels", {})

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
    for field in each.value.schema :
    merge(
      {
        name        = field.name
        type        = field.type
        mode        = lookup(field, "mode", "NULLABLE")
        description = lookup(field, "description", null)
      },
      (field.type == "RECORD" && lookup(field, "fields", null) != null)
      ? { fields = [
          for sub_field in field.fields :
          merge(
            {
              name        = sub_field.name
              type        = sub_field.type
              mode        = lookup(sub_field, "mode", "NULLABLE")
              description = lookup(sub_field, "description", null)
            },
            (sub_field.type == "RECORD" && lookup(sub_field, "fields", null) != null)
            ? { fields = [
                for third_level_field in sub_field.fields :
                merge(
                  {
                    name        = third_level_field.name
                    type        = third_level_field.type
                    mode        = lookup(third_level_field, "mode", "NULLABLE")
                    description = lookup(third_level_field, "description", null)
                  },
                  # No further nesting handled here; if more levels exist, this needs extension
                  {}
                )
              ] }
            : {}
          )
        ] }
      : {}
    )
  ])
} 