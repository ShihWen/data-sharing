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

## Local Development

1. Set up GCP credentials:
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

2. Initialize Terraform:
```bash
cd terraform
terraform init
```

3. Plan changes:
```bash
terraform plan -var-file=environments/dev.tfvars
```

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
