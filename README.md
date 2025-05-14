# Data Sharing Infrastructure

This project manages the infrastructure for data sharing using Terraform and Jenkins CI/CD pipeline.

## Project Structure

```
.
├── Jenkinsfile              # Jenkins pipeline configuration
├── README.md               # Project documentation
└── terraform/              # Terraform configurations
    ├── environments/       # Environment-specific variables
    ├── bigquery_datasets/  # BigQuery dataset configurations
    └── bigquery_tables/    # BigQuery table configurations
```

## Environment Setup

The project supports two environments:
- Development (dev)
- Production (main)

Each environment:
- Has its own GCP project
- Uses a separate service account
- Maintains state in a dedicated GCS bucket

## Prerequisites

- Terraform >= 1.0.0
- Google Cloud SDK
- Jenkins with required plugins:
  - Terraform
  - Credentials
  - Pipeline

## Development Workflow

1. Create feature branch from `dev`
2. Make changes and test locally
3. Create PR to `dev` branch
4. After approval and merge, changes are automatically applied to dev environment
5. Create PR from `dev` to `main` for production deployment
6. Production deployment requires manual approval

## CI/CD Pipeline

The Jenkins pipeline:
1. Authenticates with GCP
2. Initializes Terraform
3. Validates configurations
4. Plans changes
5. Applies changes (with approval for production)

## Security Notes

- Service account keys are managed through Jenkins Credentials
- Production deployments require manual approval
- State files are stored in environment-specific GCS buckets

## Adding New Datasets and Tables

### Adding a New Dataset
1. **Edit the `datasets.yaml` file**:
   - Navigate to `terraform/config/datasets.yaml`.
   - Add a new entry under `datasets` with the following fields:
     - `id`: Unique identifier for the dataset.
     - `friendly_name`: A user-friendly name for the dataset.
     - `description`: A brief description of the dataset.
     - `labels`: Key-value pairs for labeling the dataset.
     - `access_rules`: Define access roles and groups.

   Example:
   ```yaml
   - id: "new_dataset"
     friendly_name: "New Dataset"
     description: "Description of the new dataset"
     labels:
       environment: "development"
       purpose: "new_purpose"
     access_rules:
       - role: "OWNER"
         special_group: "projectOwners"
       - role: "READER"
         special_group: "projectReaders"
   ```

2. **Update the `dataset_ids` Mapping**:
   - Edit `terraform/bigquery_tables/main.tf`.
   - Add a new entry to the `dataset_ids` map in the `locals` block for the new dataset.

   Example:
   ```hcl
   locals {
     dataset_ids = {
       "data_sharing_dataset_id" = var.data_sharing_dataset_id
       "analytics_dataset_id"    = var.analytics_dataset_id
       "new_dataset_id"          = var.new_dataset_id  # Add this line
     }
   }
   ```

3. **Declare the New Variable**:
   - Ensure the new dataset ID variable is declared in `variables.tf` within the `bigquery_tables` module.

4. **Pass the Variable**:
   - Update the root `main.tf` to pass the new dataset ID to the `bigquery_tables` module.

5. **Deploy the Changes**:
   - Run `terraform plan` and `terraform apply` to deploy the new dataset.

### Adding a New Table
1. **Create a YAML Configuration File**:
   - Navigate to `terraform/bigquery_tables/<dataset_name>/`.
   - Create a new YAML file for the table with the following fields:
     - `dataset_id_var_name`: The variable name for the dataset ID.
     - `table_id`: Unique identifier for the table.
     - `description`: A brief description of the table.
     - `schema`: Define the table schema with fields, types, and modes.
     - `clustering`: (Optional) Columns to cluster the table by.
     - `time_partitioning`: (Optional) Define time-based partitioning.
     - `labels`: Key-value pairs for labeling the table.

   Example:
   ```yaml
   dataset_id_var_name: "data_sharing_dataset_id"
   table_id: "new_table"
   description: "Description of the new table"
   schema:
     - {name: "field1", type: "STRING", mode: "REQUIRED", description: "Description of field1"}
     - {name: "field2", type: "INTEGER", mode: "NULLABLE", description: "Description of field2"}
   clustering:
     - "field1"
   time_partitioning:
     type: "DAY"
     field: "field2"
   labels:
     data_sensitivity: "medium"
     purpose: "new_purpose"
   ```

2. **Ensure the Dataset ID Variable is Declared**:
   - Make sure the dataset ID variable referenced in `dataset_id_var_name` is declared in `variables.tf`.

3. **Deploy the Changes**:
   - Run `terraform plan` to ensure the configuration is correct and no errors occur.
   - Run `terraform apply` to deploy the new table.

These steps ensure that new datasets and tables are added following the infrastructure-as-code best practices, allowing for easy management and scalability.
