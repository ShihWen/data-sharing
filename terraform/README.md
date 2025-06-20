# Terraform Infrastructure Management

This directory contains the Terraform configurations for managing the comprehensive data sharing infrastructure, including Airflow orchestration, BigQuery analytics, and AWS S3 data transfer capabilities.

## 🏗️ Architecture Overview

The infrastructure is built with a modular approach:

- **Airflow Module**: Manages VM-based Airflow instance with Docker containerization
- **BigQuery Datasets**: YAML-driven dynamic dataset creation and management
- **BigQuery Tables**: Schema-driven table provisioning with Bronze/Silver/Gold tiers
- **Transfer Jobs**: Automated S3 to BigQuery data ingestion
- **Service Accounts**: Dedicated security roles for each component

## 📁 Directory Structure

```
terraform/
├── main.tf                    # Root module orchestrating all components
├── variables.tf               # Input variables and configuration
├── outputs.tf                 # Output values for reference
├── backend.tf                 # Terraform state backend configuration
├── environments/              # Environment-specific configurations
│   └── dev.tfvars            # Development environment variables
├── airflow/                   # 🚁 Airflow orchestration infrastructure
│   ├── main.tf               # VM, service accounts, and permissions
│   ├── docker/               # Docker Compose and DAG configurations
│   │   ├── docker-compose.yml # Airflow services definition
│   │   ├── config/           # Airflow configuration files
│   │   └── dags/             # Data pipeline DAGs
│   ├── templates/            # VM startup scripts and connection templates
│   ├── README.md             # Comprehensive Airflow documentation
│   └── README_AUTO_CONNECTIONS.md # Auto-connection setup guide
├── bigquery_datasets/         # 📊 Dynamic dataset management
│   ├── main.tf               # Dataset creation with YAML configuration
│   └── config/               # YAML-based dataset definitions
│       └── datasets.yaml     # Centralized dataset specifications
├── bigquery_tables/          # 📋 Schema-driven table provisioning
│   ├── main.tf              # Table module with dynamic configuration
│   ├── tpe_mrt_bronze/      # Bronze tier: Raw Taipei MRT data
│   └── tpe_mrt_silver/      # Silver tier: Cleaned and validated data
└── transfer_jobs/           # 🔄 Automated S3 to BigQuery transfers
    └── main.tf             # Data transfer job configurations
```

## 🎯 Key Features

### YAML-Driven Configuration
The infrastructure uses a dynamic configuration system:

```yaml
# datasets.yaml example
datasets:
  - id: "tpe_mrt_bronze"
    friendly_name: "Taipei MRT Bronze Tier"
    description: "Raw Taipei Metro system data"
    labels:
      environment: "dev"
      data_tier: "bronze"
      source: "s3_transfer"
    access_rules:
      - role: "OWNER"
        special_group: "projectOwners"
      - role: "WRITER"
        user_by_email: "airflow-scheduler-sa@open-data-v2-cicd.iam.gserviceaccount.com"
```

### Infrastructure as Code Benefits
- **Version Control**: All configurations are tracked in Git
- **Reproducibility**: Identical infrastructure across environments
- **Automation**: Jenkins CI/CD pipeline for deployment
- **Modularity**: Reusable components with clear interfaces

### Security and Permissions
- **Service Account Isolation**: Dedicated SAs for each component
- **Least Privilege**: Minimal required permissions
- **Automated Role Binding**: Dynamic permission assignment
- **State Encryption**: Terraform state secured in GCS

## 🚀 Adding New Resources

### Adding a New Dataset

**Step 1: Update Dataset Configuration**
```bash
# Edit the datasets configuration
nano bigquery_datasets/config/datasets.yaml
```

Add your dataset:
```yaml
- id: "your_dataset_name"                    # Used as reference in tables
  friendly_name: "Your Dataset Display Name"
  description: "Comprehensive description of the dataset purpose"
  labels:
    environment: "dev"                       # or "prod"
    data_tier: "bronze"                      # bronze|silver|gold
    domain: "your_business_domain"           # e.g., "transportation", "finance"
    owner: "your_team"                       # responsible team
    source: "s3_transfer"                    # data source type
  access_rules:
    - role: "OWNER"
      special_group: "projectOwners"
    - role: "WRITER"
      user_by_email: "airflow-scheduler-sa@open-data-v2-cicd.iam.gserviceaccount.com"
    - role: "READER"
      special_group: "projectReaders"
```

**Step 2: Apply Changes**
```bash
# Review the changes
terraform plan

# Apply the dataset creation
terraform apply
```

That's it! The dataset will be automatically:
- ✅ Created in BigQuery with specified configuration
- ✅ Available to all modules through the `dataset_outputs` map
- ✅ Accessible for table creation with proper permissions
- ✅ Ready for Airflow DAG integration
- ✅ Configured for transfer jobs if needed

### Adding New Tables

**Step 1: Create Table Directory**
```bash
mkdir bigquery_tables/your_dataset_name
```

**Step 2: Define Table Schema**
```bash
# Create table YAML file
nano bigquery_tables/your_dataset_name/your_table.yaml
```

Example table configuration:
```yaml
table_id: "your_table_name"
dataset_id_var_name: "your_dataset_name"     # Must match dataset.id from datasets.yaml
description: "Detailed table description with purpose and data sources"
labels:
  data_source: "aws_s3"                      # source system
  data_type: "transactional"                 # transactional|analytical|reference
  tier: "bronze"                             # bronze|silver|gold
  update_frequency: "daily"                  # daily|hourly|batch|streaming

schema:
  - name: "transaction_id"
    type: "STRING"
    mode: "REQUIRED"
    description: "Unique identifier for each transaction"
  - name: "amount"
    type: "NUMERIC"
    mode: "NULLABLE"
    description: "Transaction amount in local currency"
  - name: "timestamp"
    type: "TIMESTAMP"
    mode: "REQUIRED"
    description: "UTC timestamp of transaction occurrence"

# Optional: Table optimization
clustering:
  - "transaction_id"
  - "timestamp"

time_partitioning:
  type: "DAY"
  field: "timestamp"
  require_partition_filter: true
```

**Step 3: Apply Changes**
```bash
terraform plan && terraform apply
```

### Adding Transfer Jobs (S3 to BigQuery)

Transfer jobs are automatically configured for datasets. To customize:

```bash
# Edit transfer job configuration
nano transfer_jobs/main.tf
```

Add or modify transfer configurations:
```hcl
resource "google_bigquery_data_transfer_config" "your_dataset_transfer" {
  display_name           = "Your Dataset S3 Transfer"
  project               = var.project_id
  location              = "asia-east1"
  data_source_id        = "amazon_s3"
  schedule              = "every day 02:00"
  destination_dataset_id = var.dataset_ids["your_dataset_name"]
  
  params = {
    destination_table_name_template = "your_table_{run_date}"
    file_format                     = "CSV"
    max_bad_records                = "1000"
    skip_leading_rows              = "1"
    write_disposition              = "WRITE_APPEND"
    data_path_template             = "s3://${var.s3_bucket}/your_dataset/*"
    access_key_id                  = var.aws_access_key
    secret_access_key              = var.aws_secret_key
  }

  service_account_name = google_service_account.transfer_sa.email
  
  depends_on = [
    google_service_account_iam_binding.transfer_sa_binding
  ]
}
```

## 🔧 CI/CD Integration

### Jenkins Pipeline Integration

The infrastructure integrates seamlessly with the Jenkins pipeline:

1. **Environment Setup**: Pipeline authenticates with GCP and configures state backend
2. **Resource Import**: Handles existing resources to avoid conflicts
3. **VM Health Checking**: Intelligently determines if Airflow VM needs recreation
4. **Targeted Planning**: Creates efficient plans based on resource state
5. **Automated Deployment**: Applies infrastructure changes with proper dependencies

### Pipeline-Aware Configuration

Key environment variables used by the pipeline:
- `DEV_GCP_PROJECT_ID`: Target GCP project
- `DEV_TF_STATE_BUCKET`: Terraform state storage
- `AIRFLOW_BUCKET`: GCS bucket for Airflow DAGs and logs
- `S3_BUCKET`: Source AWS S3 bucket for data ingestion

## 📊 Data Architecture Patterns

### Data Tier Strategy

**Bronze Tier (Raw Data)**
- Direct S3 to BigQuery transfers
- Minimal transformation
- Preserves original data structure
- Optimized for ingestion speed

**Silver Tier (Clean Data)**
- Processed via Airflow DAGs
- Data quality validation
- Standardized schemas
- Business rule application

**Gold Tier (Analytics-Ready)**
- Aggregated and enriched data
- Optimized for queries
- Business-specific transformations
- Ready for reporting and ML

### Current Implementation

**TPE MRT Dataset**
- **Bronze**: Raw Taipei Metro data from S3
- **Silver**: Cleaned and validated transit data
- **Gold**: (Future) Analytics-ready aggregations

**Fruit Dataset**
- **Example**: Testing and validation dataset
- **Pattern**: Template for new dataset onboarding

## 🔒 Security Architecture

### Service Account Strategy
- **Airflow SA**: Manages workflow execution and BigQuery operations
- **Transfer SA**: Handles S3 to BigQuery data transfers
- **Pipeline SA**: Used by Jenkins for infrastructure deployment

### Permission Model
- **Dataset-level**: Granular access control per dataset
- **Role-based**: Standard roles (OWNER, WRITER, READER)
- **Service Account**: Automated access for system components
- **Group-based**: Human access via Google Groups

### State Management Security
- **GCS Backend**: Encrypted state storage
- **Version Control**: State file versioning enabled
- **Access Logging**: Full audit trail of state changes
- **Isolation**: Environment-specific state buckets

## 🛠️ Local Development

### Prerequisites
```bash
# Required tools
terraform --version  # >= 1.11.3
gcloud --version     # Latest
docker --version     # For local Airflow testing
```

### Development Workflow
```bash
# 1. Clone and setup
git clone <repo-url>
cd data-sharing/terraform

# 2. Configure GCP authentication
gcloud auth application-default login
gcloud config set project open-data-v2-cicd

# 3. Initialize Terraform
terraform init

# 4. Plan changes
terraform plan -var-file="environments/dev.tfvars"

# 5. Apply changes (dev environment)
terraform apply -var-file="environments/dev.tfvars"
```

### Testing New Configurations
```bash
# Validate configuration syntax
terraform validate

# Format configuration files
terraform fmt -recursive

# Check for security issues (if using tfsec)
tfsec .

# Plan with detailed output
terraform plan -detailed-exitcode
```

## 🔍 Monitoring and Troubleshooting

### Resource Monitoring
```bash
# Check Airflow VM status
gcloud compute instances describe airflow-vm --zone=asia-east1-b

# Monitor transfer jobs
bq ls -j --max_results=10 open-data-v2-cicd

# Check dataset access permissions
bq show --format=prettyjson open-data-v2-cicd:tpe_mrt_bronze
```

### Common Issues and Solutions

**Issue**: Dataset creation fails with permission errors
**Solution**: Verify service account has `bigquery.dataOwner` role

**Issue**: Transfer jobs fail with S3 access errors  
**Solution**: Check AWS credentials and S3 bucket permissions

**Issue**: Terraform state conflicts
**Solution**: Use `terraform import` for existing resources

**Issue**: Airflow can't access BigQuery
**Solution**: Verify service account key is properly mounted

## 📚 Best Practices

### Configuration Management
1. **Use YAML**: Leverage YAML for readable, maintainable configurations
2. **Version Everything**: All configurations should be in version control
3. **Environment Isolation**: Separate state and resources per environment
4. **Documentation**: Keep inline documentation up to date

### Security Best Practices
1. **Least Privilege**: Grant minimal required permissions
2. **Service Account Keys**: Secure key management and rotation
3. **State Security**: Encrypt and protect Terraform state
4. **Access Auditing**: Regular review of permissions and access

### Development Best Practices
1. **Plan First**: Always run `terraform plan` before applying
2. **Small Changes**: Make incremental, reviewable changes
3. **Test Locally**: Validate configurations before deployment
4. **Monitor Deployments**: Watch for errors and performance issues

---

For more detailed information:
- **Airflow**: See `airflow/README.md` for Airflow-specific documentation
- **Scripts**: See `../scripts/README.md` for operational scripts
- **Pipeline**: Check `../Jenkinsfile` for CI/CD configuration 