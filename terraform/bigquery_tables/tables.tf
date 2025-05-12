# terraform/bigquery_tables/tables.tf

locals {
  # Find all .yaml files in the schemas directory
  schema_path = "${path.module}/schemas"
  table_schema_files = fileset(local.schema_path, "**/*.yaml")

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
        yamldecode(file("${local.schema_path}/${fpath}"))
      )
      dataset_name = split("/", fpath)[0]
    }
  }

  # Validate all required fields are present in schemas
  schema_validation = [
    for fpath, config in local.table_configs : {
      file_path = fpath
      validation_errors = concat(
        !can(config.config.dataset_id_var_name) ? ["Missing dataset_id_var_name"] : [],
        !can(config.config.table_id) ? ["Missing table_id"] : [],
        !can(config.config.schema) ? ["Missing schema definition"] : [],
        try(length(config.config.schema), 0) == 0 ? ["Schema cannot be empty"] : []
      )
    }
  ]

  # Check if any tables should be created
  should_create_tables = length(local.table_configs) > 0
  
  # Define environment-specific settings
  is_prod = var.deployment_env == "prod"
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

  deletion_protection = local.is_prod

  depends_on = [
    null_resource.schema_validation
  ]

  lifecycle {
    prevent_destroy = false  # We'll use deletion_protection instead for environment-specific protection
  }
}

