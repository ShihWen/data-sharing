# Data Sharing Platform

This repository contains the infrastructure code for managing BigQuery datasets and tables using Terraform.

## Project Structure

```
terraform/
├── bigquery_datasets/
│   ├── configs/
│   │   └── datasets.yaml    # Dataset definitions
│   ├── datasets.tf          # Dataset creation logic
│   └── variables.tf         # Module variables
├── bigquery_tables/
│   ├── schemas/            # Table schema definitions
│   │   ├── my_dataset_sales/
│   │   │   └── orders.yaml
│   │   └── my_dataset_marketing/
│   ├── tables.tf           # Table creation logic
│   └── variables.tf        # Module variables
├── environments/
│   ├── dev.tfvars         # Development environment variables
│   └── prod.tfvars        # Production environment variables
├── main.tf                # Root module configuration
├── variables.tf           # Root variables
└── backend.tf            # Terraform backend configuration
```

## Adding a New Dataset

To add a new BigQuery dataset, follow these steps:

1. Add the dataset configuration to `terraform/bigquery_datasets/configs/datasets.yaml`:
   ```yaml
   datasets:
     # ... existing datasets ...
     - dataset_id_var_name: "new_dataset_id"
       friendly_name: "New Dataset Name"
       description: "Description of the new dataset"
       dataset_id: "new_dataset_dev"  # For dev environment
       labels:
         team: "your_team"
         goog-terraform-provisioned: "true"
   ```

2. Update the `_dynamic_dataset_ids` map in environment tfvars files:
   
   In `terraform/environments/dev.tfvars`:
   ```hcl
   _dynamic_dataset_ids = {
     # ... existing mappings ...
     new_dataset_id = "new_dataset_dev"
   }
   ```

   In `terraform/environments/prod.tfvars`:
   ```hcl
   _dynamic_dataset_ids = {
     # ... existing mappings ...
     new_dataset_id = "new_dataset_prod"
   }
   ```

3. Create a directory for table schemas (if you plan to add tables):
   ```bash
   mkdir -p terraform/bigquery_tables/schemas/my_dataset_new
   ```

## Adding Tables to a Dataset

1. Create a new YAML file in the corresponding dataset directory under `terraform/bigquery_tables/schemas/`:
   ```yaml
   dataset_id_var_name: "new_dataset_id"  # Must match the dataset_id_var_name from datasets.yaml
   table_id: "your_table_name"
   description: "Description of your table"
   schema:
     - {name: "column1", type: "STRING",  mode: "REQUIRED", description: "First column"}
     - {name: "column2", type: "INTEGER", mode: "NULLABLE", description: "Second column"}
   labels:
     data_sensitivity: "low"
     source_system: "your_system"
   ```

## Deployment

The deployment is handled by Jenkins CI/CD pipeline. The pipeline will:
1. Initialize Terraform
2. Validate the configuration
3. Plan the changes
4. Apply the changes (with approval for production)

## Environment-Specific Configurations

- Development environment uses the `dev.tfvars` file
- Production environment uses the `prod.tfvars` file
- Each environment has its own state file in GCS

## Best Practices

1. Always test changes in the development environment first
2. Use meaningful names and descriptions for datasets and tables
3. Add appropriate labels for better resource management
4. Document any special configurations or requirements
5. Follow the existing naming conventions

## Notes

- Dataset IDs in production should follow the pattern: `dataset_name_prod`
- Dataset IDs in development should follow the pattern: `dataset_name_dev`
- Table schemas should be well-documented with clear descriptions
- Labels should be consistent across resources
