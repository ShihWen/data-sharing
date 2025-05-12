# terraform/bigquery_tables/tables.tf

locals {
  # Debug variables for path resolution
  _debug_current_path_module = path.module
  _debug_current_path_root  = path.root
  _debug_current_path_cwd   = path.cwd
  _debug_schema_path        = "${path.module}/schemas"

  # Find all .yaml files in the schemas directory and its subdirectories
  table_schema_files = fileset(local._debug_schema_path, "**/*.yaml")

  # Debug: Print the first file content if any exists
  _debug_first_file_content = length(local.table_schema_files) > 0 ? yamldecode(file("${local._debug_schema_path}/${tolist(local.table_schema_files)[0]}")) : {}

  # Create a map of table configurations from the YAML files
  table_configs = {
    for fpath in local.table_schema_files : fpath => {
      config = merge(
        {
          description = null
          labels     = {}
          clustering = null
          time_partitioning = null
        },
        yamldecode(file("${local._debug_schema_path}/${fpath}"))
      )
      dataset_name = split("/", fpath)[0]
    }
  }

  # Debug outputs
  _debug = {
    paths = {
      module_path = local._debug_current_path_module
      root_path   = local._debug_current_path_root
      cwd_path    = local._debug_current_path_cwd
      schema_path = local._debug_schema_path
    }
    found_files = {
      files_found = local.table_schema_files
      file_count  = length(local.table_schema_files)
    }
    first_file_content = local._debug_first_file_content
    table_configs      = local.table_configs
  }

  # Validate all required fields are present in schemas
  schema_validation = [
    for fpath, config in local.table_configs : {
      file_path = fpath
      validation_errors = concat(
        !can(config.config.dataset_id_var_name) ? ["Missing dataset_id_var_name"] : [],
        !can(config.config.table_id) ? ["Missing table_id"] : [],
        !can(config.config.schema) ? ["Missing schema definition"] : []
      )
    }
  ]

  # Additional validation for dynamic dataset IDs
  dataset_id_validation = {
    for fpath, config in local.table_configs : fpath => {
      dataset_id_var_name = try(config.config.dataset_id_var_name, "NOT_FOUND")
      dataset_id_value = try(var._dynamic_dataset_ids[config.config.dataset_id_var_name], "NOT_FOUND")
    }
  }

  # Check if any tables should be created
  should_create_tables = length(local.table_configs) > 0
  
  # Define environment-specific settings
  is_prod = var.deployment_env == "prod"
}

# Output debug information
output "debug_info" {
  value = local._debug
}

# Output validation information
output "validation_info" {
  value = {
    schema_validation = local.schema_validation
    dataset_id_validation = local.dataset_id_validation
    should_create_tables = local.should_create_tables
    table_count = length(local.table_configs)
  }
}

# Fail if any validation errors are found
resource "null_resource" "schema_validation" {
  count = length(flatten([for v in local.schema_validation : v.validation_errors])) > 0 ? 1 : 0

  provisioner "local-exec" {
    command = <<EOF
      echo "Schema validation errors found:"
      ${join("\n", flatten([
        for v in local.schema_validation :
        [for err in v.validation_errors : "File ${v.file_path}: ${err}"]
      ]))}
      exit 1
    EOF
  }
}

# Output the table configurations for verification
output "table_configurations" {
  value = {
    for k, v in local.table_configs : k => {
      dataset_id = try(var._dynamic_dataset_ids[v.config.dataset_id_var_name], "NOT_FOUND")
      table_id   = v.config.table_id
      schema     = try(v.config.schema, [])
    }
  }
}

# Create tables only if we have valid configurations
resource "google_bigquery_table" "this" {
  for_each = local.should_create_tables ? local.table_configs : {}

  project    = var.gcp_project_id
  dataset_id = var._dynamic_dataset_ids[each.value.config.dataset_id_var_name]
  table_id   = each.value.config.table_id
  
  description = try(each.value.config.description, null)
  labels      = try(each.value.config.labels, {})

  schema = jsonencode(each.value.config.schema)

  dynamic "time_partitioning" {
    for_each = try(each.value.config.time_partitioning, null) != null ? [each.value.config.time_partitioning] : []
    content {
      type          = time_partitioning.value.type
      field         = try(time_partitioning.value.field, null)
      expiration_ms = try(time_partitioning.value.expiration_ms, null)
    }
  }

  clustering = try(each.value.config.clustering, null)

  deletion_protection = local.is_prod ? true : false

  depends_on = [
    null_resource.schema_validation,
    google_bigquery_dataset.my_dataset_sales,
    google_bigquery_dataset.my_dataset_marketing
  ]

  lifecycle {
    prevent_destroy = local.is_prod
  }
}

