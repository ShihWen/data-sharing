terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 4.40.0, < 5.0.0"
    }
  }
}

locals {
  # Find all .yaml files that define views or materialized views
  all_yaml_files = fileset(path.module, "**/*.yaml")

  # Parse the yaml files and categorize them
  view_configs = {
    for file in local.all_yaml_files : trimsuffix(file, ".yaml") => {
      yaml_config = yamldecode(file("${path.module}/${file}"))
      sql_file_path = "${path.module}/${trimsuffix(file, ".yaml")}.sql"
    }
  }

  regular_views = {
    for k, v in local.view_configs : k => v if lookup(v.yaml_config, "view_id", null) != null
  }

  materialized_views = {
    for k, v in local.view_configs : k => v if lookup(v.yaml_config, "materialized_view_id", null) != null
  }
}

resource "google_bigquery_table" "views" {
  for_each = local.regular_views

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

resource "google_bigquery_materialized_view" "materialized_views" {
  for_each = local.materialized_views

  project      = var.project_id
  dataset_id   = var.dataset_ids[each.value.yaml_config.dataset_id_var_name]
  table_id     = each.value.yaml_config.materialized_view_id
  description  = lookup(each.value.yaml_config, "description", null)
  labels       = lookup(each.value.yaml_config, "labels", {})

  deletion_protection = false

  query = templatefile(each.value.sql_file_path, {
    project_id = var.project_id,
    datasets   = var.dataset_ids
  })

  enable_refresh      = lookup(each.value.yaml_config.options, "enable_refresh", false)
  refresh_interval_ms = lookup(each.value.yaml_config.options, "enable_refresh", false) ? lookup(each.value.yaml_config.options, "refresh_interval_minutes", 30) * 60000 : null

  allow_non_incremental_definition = true

  time_partitioning {
    type  = lookup(each.value.yaml_config.partitioning, "type", null)
    field = lookup(each.value.yaml_config.partitioning, "field", null)
  }

  clustering = lookup(each.value.yaml_config.clustering, "fields", null)
} 