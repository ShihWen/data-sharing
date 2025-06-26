locals {
  # Find all .yaml files that define views
  view_yaml_files = fileset(path.module, "**/*.yaml")

  # Parse the yaml files
  view_configs = {
    for file in local.view_yaml_files : trimsuffix(file, ".yaml") => {
      yaml_config = yamldecode(file("${path.module}/${file}"))
      # Assume the SQL file has the same base name as the YAML file, but with a .sql extension
      sql_file_path = "${path.module}/${trimsuffix(file, ".yaml")}.sql"
    }
  }
}

resource "google_bigquery_table" "views" {
  for_each = local.view_configs

  project      = var.project_id
  dataset_id   = var.dataset_ids[each.value.yaml_config.dataset_id_var_name]
  table_id     = each.value.yaml_config.view_id
  description  = lookup(each.value.yaml_config, "description", null)
  labels       = lookup(each.value.yaml_config, "labels", {})

  deletion_protection = false

  view {
    query          = templatefile(each.value.sql_file_path, {
      project_id = var.project_id,
      datasets = var.dataset_ids
    })
    use_legacy_sql = false
  }
} 