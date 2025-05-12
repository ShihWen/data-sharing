# terraform/bigquery_tables/tables.tf

locals {
  _debug_current_path_module = path.module # Should be ./bigquery_tables when run from terraform/
  _debug_schemas_dir_to_scan = "${path.module}/schemas" # e.g., ./bigquery_tables/schemas

  # Find all .yaml files in the schemas directory and its subdirectories
  table_schema_files = fileset("${path.module}/schemas", "**/*.yaml")

  # Create a map of table configurations from the YAML files
  # The key for the map will be the file path (unique identifier)
  # The value will be the parsed YAML content with validation
  table_configs = {
    for fpath in local.table_schema_files : fpath => {
      # Merge the parsed YAML with default values and validate required fields
      config = merge(
        {
          description = null
          labels     = {}
          clustering = null
          time_partitioning = null
        },
        yamldecode(file("${path.module}/schemas/${fpath}"))
      )
      
      # Extract dataset name from path for depends_on configuration
      dataset_name = split("/", fpath)[0]
    }
  }

  # Debug outputs
  _debug = {
    found_schema_files = local.table_schema_files
    table_configs = local.table_configs
  }

  # Validate all required fields are present in schemas
  # This will fail terraform plan if any required fields are missing
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
}

# Output debug information
output "debug_info" {
  value = local._debug
}

# Fail if any validation errors are found
resource "null_resource" "schema_validation" {
  count = length(flatten([for v in local.schema_validation : v.validation_errors])) > 0 ? "fail" : 0

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

resource "google_bigquery_table" "this" {
  for_each = local.table_configs

  project    = var.gcp_project_id
  dataset_id = var._dynamic_dataset_ids[each.value.config.dataset_id_var_name]
  table_id   = each.value.config.table_id
  
  description = try(each.value.config.description, null)
  labels      = try(each.value.config.labels, {})

  # Schema is required, so we don't use try() here
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

  # Set deletion_protection based on environment
  deletion_protection = var.deployment_env == "prod" ? true : false

  # Dynamic depends_on based on the dataset the table belongs to
  depends_on = [
    null_resource.schema_validation,
    google_bigquery_dataset.my_dataset_sales,
    google_bigquery_dataset.my_dataset_marketing
  ]

  lifecycle {
    # Prevent destruction of production tables unless deletion_protection is first set to false
    prevent_destroy = var.deployment_env == "prod"
  }
}

