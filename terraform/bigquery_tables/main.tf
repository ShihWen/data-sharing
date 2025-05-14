locals {
  table_files = fileset(path.module, "*/*/*.yaml")
  table_configs = {
    for file in local.table_files : file => yamldecode(file(file))
  }
  
  # Map dataset variable names to their values
  dataset_ids = {
    "data_sharing_dataset_id" = var.data_sharing_dataset_id
    "analytics_dataset_id"    = var.analytics_dataset_id
  }
}

resource "google_bigquery_table" "tables" {
  for_each = local.table_configs

  dataset_id = local.dataset_ids[each.value.dataset_id_var_name]
  table_id   = each.value.table_id
  project    = var.project_id
  description = each.value.description

  labels = each.value.labels

  dynamic "time_partitioning" {
    for_each = each.value.time_partitioning != null ? [each.value.time_partitioning] : []
    content {
      type  = time_partitioning.value.type
      field = time_partitioning.value.field
    }
  }

  # Direct clustering configuration
  clustering = each.value.clustering

  schema = jsonencode([
    for field in each.value.schema : {
      name        = field.name
      type        = field.type
      mode        = field.mode
      description = field.description
    }
  ])
} 