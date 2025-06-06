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
   datasets:
     - id: "your_new_dataset"
       friendly_name: "Your New Dataset"
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

That's it! The dataset will be automatically picked up by all modules. The dataset ID you specify in the `id` field will be used as the reference key in table configurations.

### Adding New Tables

1. Create a new YAML file in the appropriate directory under `bigquery_tables/`:
   ```yaml
   table_id: "your_table_name"
   dataset_id_var_name: "your_dataset_id"  # Must match the dataset's 'id' field from datasets.yaml
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

Note: The `dataset_id_var_name` should exactly match the `id` field of the dataset you defined in `datasets.yaml`.

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

## Best Practices

1. Always add descriptive labels to datasets and tables
2. Include comprehensive descriptions for all resources
3. Follow the naming convention for dataset tiers (bronze, silver, gold)
4. Use appropriate access rules for data security
5. Document schema changes in table YAML files
6. Keep dataset IDs consistent between dataset and table configurations 