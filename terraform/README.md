# Terraform Infrastructure Management

This directory contains the Terraform configurations for managing the data sharing infrastructure.

## Directory Structure

```
terraform/
├── airflow/              # Airflow VM and related resources
├── bigquery_datasets/    # Dataset definitions and configurations
│   └── config/          # Dataset YAML configurations
├── bigquery_tables/     # Table definitions and schemas
│   ├── tpe_mrt_bronze/  # Bronze tier tables
│   └── tpe_mrt_silver/  # Silver tier tables
├── transfer_jobs/       # Data transfer job configurations
└── environments/        # Environment-specific configurations
```

## Adding New Resources

### Adding a New Dataset

1. Add the dataset configuration to `bigquery_datasets/config/datasets.yaml`:
   ```yaml
   - id: "your_new_dataset"          # This ID will be used as reference in tables
     friendly_name: "Your Dataset"
     description: "Description of your dataset"
     labels:
       environment: "development"
       domain: "your_domain"
       data_tier: "bronze|silver|gold"
       owner: "your_team"
     access_rules:
       - role: "OWNER"
         special_group: "projectOwners"
       - role: "WRITER"
         special_group: "projectWriters"
       - role: "READER"
         special_group: "projectReaders"
   ```

2. (Optional) Add Tables:
   - Create a new directory for your tables:
     ```bash
     mkdir bigquery_tables/your_new_dataset
     ```
   - Create table YAML files in this directory:
     ```yaml
     # your_table.yaml
     table_id: "your_table_name"
     dataset_id_var_name: "your_new_dataset"  # Must match dataset.id from step 1
     description: "Table description"
     labels:
       data_source: "source_name"
       data_type: "type"
       tier: "bronze|silver|gold"
     
     schema:
       - name: "column_name"
         type: "STRING|INTEGER|DATE|etc"
         mode: "NULLABLE|REQUIRED|REPEATED"
         description: "Column description"
     ```

3. (Optional) Add Transfer Jobs:
   If you need to transfer data to your new dataset, add transfer job configurations in `transfer_jobs/main.tf`:
   ```hcl
   resource "google_bigquery_data_transfer_config" "your_transfer" {
     display_name           = "Your Data Transfer"
     project               = var.project_id
     location              = "asia-east1"
     data_source_id        = "amazon_s3"
     schedule              = var.schedule
     destination_dataset_id = var.dataset_ids["your_new_dataset"]
     service_account_name  = google_service_account.transfer_sa.email
     # ... rest of configuration
   }
   ```

4. Apply Changes:
   ```bash
   # Review changes
   terraform plan

   # Apply changes
   terraform apply
   ```

That's it! The dataset will be automatically:
- Created in BigQuery with the specified configuration
- Available to all modules through the dataset_ids map
- Accessible for table creation
- Available for transfer jobs
- Available for Airflow tasks

No other file modifications are needed thanks to the dynamic configuration system.

## Best Practices

1. Always add descriptive labels to datasets and tables
2. Include comprehensive descriptions for all resources
3. Follow the naming convention for dataset tiers (bronze, silver, gold)
4. Use appropriate access rules for data security
5. Document schema changes in table YAML files
6. Keep dataset IDs consistent between dataset and table configurations
7. Use meaningful and consistent naming patterns for tables within each tier

## Infrastructure Updates

To apply infrastructure changes:

1. Review changes:
   ```bash
   terraform plan
   ```

2. Apply changes:
   ```bash
   terraform apply
   ```

## Common Patterns

### Dataset Tiers
- **Bronze**: Raw data, exactly as received from source
- **Silver**: Cleaned and validated data
- **Gold**: Analytics-ready, aggregated data

### Access Rules
- Project owners get OWNER access
- Project writers get WRITER access
- Project readers get READER access
- Additional custom access can be granted per dataset 