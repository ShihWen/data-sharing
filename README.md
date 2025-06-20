# Data Sharing Infrastructure

This project manages a comprehensive data sharing infrastructure using Terraform, Apache Airflow, and Jenkins CI/CD pipeline. The infrastructure provisions Google Cloud Platform resources for data ingestion, transformation, and analytics.

## 🏗️ Architecture Overview

The project implements a modern data platform with the following components:

- **Data Ingestion**: AWS S3 to Google BigQuery transfer jobs
- **Data Processing**: Apache Airflow for workflow orchestration
- **Data Storage**: BigQuery datasets organized in Bronze/Silver/Gold tiers
- **Infrastructure**: Terraform for Infrastructure as Code
- **CI/CD**: Jenkins pipeline for automated deployments
- **Monitoring**: Automated health checks and connection management

## 📁 Project Structure

```
.
├── Jenkinsfile                    # Jenkins CI/CD pipeline configuration
├── README.md                     # This file - project overview
├── scripts/                      # Utility scripts for operations
│   ├── README.md                # Scripts documentation
│   ├── airflow-manager.sh       # Airflow operations management
│   ├── setup_auto_connections.sh # Auto-connection setup
│   ├── update_airflow_config.sh # Airflow configuration updates
│   ├── test-connection-check.sh # Connection testing
│   └── upload_config.sh         # DAG upload to GCS
└── terraform/                   # Infrastructure as Code
    ├── README.md               # Terraform documentation
    ├── main.tf                 # Root module configuration
    ├── variables.tf            # Variable definitions
    ├── outputs.tf              # Output values
    ├── backend.tf              # Terraform state backend
    ├── environments/           # Environment-specific configurations
    │   └── dev.tfvars         # Development environment variables
    ├── airflow/               # Airflow VM and services
    │   ├── README.md          # Airflow module documentation
    │   ├── README_AUTO_CONNECTIONS.md # Auto-connection setup guide
    │   ├── main.tf            # Airflow infrastructure
    │   ├── docker/            # Docker configurations and DAGs
    │   └── templates/         # VM startup scripts and configurations
    ├── bigquery_datasets/     # BigQuery dataset configurations
    │   ├── main.tf           # Dataset module
    │   └── config/           # YAML-based dataset definitions
    │       └── datasets.yaml # Dataset configuration file
    ├── bigquery_tables/      # BigQuery table configurations
    │   ├── main.tf          # Table module
    │   ├── tpe_mrt_bronze/  # Bronze tier table definitions
    │   └── tpe_mrt_silver/  # Silver tier table definitions
    └── transfer_jobs/       # S3 to BigQuery transfer jobs
        └── main.tf         # Transfer job configurations
```

## 🌍 Environment Setup

The project supports multiple environments with isolated resources:

### Development Environment
- **GCP Project**: `open-data-v2-cicd`
- **State Bucket**: `terraform-state-data-sharing-dev-new`
- **Airflow Bucket**: `open-data-v2-cicd-airflow-storage`
- **Data Source**: `online-data-lake-thirty-three` (AWS S3)

### Production Environment
- Configured via `main` branch
- Separate GCP project and resources
- Manual approval required for deployments

## 🚀 Quick Start

### Prerequisites

- **Terraform** >= 1.11.3
- **Google Cloud SDK** with authentication
- **Jenkins** with required plugins:
  - Terraform
  - Credentials
  - Pipeline
- **Docker** and **Docker Compose** (for local development)

### Initial Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd data-sharing
   ```

2. **Configure GCP credentials**:
   ```bash
   gcloud auth application-default login
   gcloud config set project open-data-v2-cicd
   ```

3. **Initialize Terraform**:
   ```bash
   cd terraform
   terraform init
   ```

4. **Review and apply infrastructure**:
   ```bash
   terraform plan
   terraform apply
   ```

## 🔄 Development Workflow

### Branch Strategy
1. **Feature Development**: Create feature branch from `dev`
2. **Testing**: Test changes locally and create PR to `dev`
3. **Dev Deployment**: Auto-deployment on merge to `dev`
4. **Production**: Create PR from `dev` to `main` (requires approval)

### CI/CD Pipeline Stages

The Jenkins pipeline (`Jenkinsfile`) includes:

1. **Code Checkout**: Retrieves latest code
2. **DAG Change Detection**: Identifies Airflow DAG modifications
3. **DAG Upload**: Syncs DAGs to GCS bucket if changes detected
4. **Environment Setup**: GCP authentication and bucket creation
5. **Terraform Init**: Initializes Terraform with remote state
6. **Service Account Import**: Handles existing resource imports
7. **VM Status Check**: Determines if Airflow VM needs recreation
8. **Terraform Plan**: Creates execution plan (targeted if VM healthy)
9. **Terraform Apply**: Applies infrastructure changes
10. **Airflow Connections Setup**: Configures Airflow connections and variables

### Pipeline Features

- **Smart VM Management**: Avoids unnecessary VM recreation
- **Automated DAG Sync**: Only uploads DAGs when changes detected
- **Health Checking**: Validates Airflow availability before operations
- **Error Handling**: Robust error handling and recovery mechanisms

## 📊 Data Architecture

### Data Tiers
- **Bronze**: Raw data directly from S3 sources
- **Silver**: Cleaned and validated data
- **Gold**: Analytics-ready, aggregated data

### Current Datasets
- **TPE MRT**: Taipei Metro system data (Bronze/Silver tiers)

### Data Flow
```
AWS S3 → BigQuery (Bronze) → Airflow Processing → BigQuery (Silver/Gold)
```

## 🔒 Security & Permissions

- **Service Accounts**: Dedicated service accounts for each component
- **State Management**: Encrypted state files in GCS with versioning
- **Connection Management**: Automated and secure connection setup
- **Access Control**: Role-based access to datasets and resources

## 📈 Monitoring & Operations

### Airflow Management
- **Web UI**: Available at `http://<VM_IP>:8081`
- **Auto-Connections**: Automatic setup on VM restart
- **Health Checks**: Automated monitoring and recovery

### Operational Scripts
- `airflow-manager.sh`: Comprehensive Airflow operations
- `setup_auto_connections.sh`: Auto-connection configuration
- `test-connection-check.sh`: Connection testing utilities

## 🛠️ Adding New Resources

### Adding a New Dataset
1. Edit `terraform/bigquery_datasets/config/datasets.yaml`
2. Add dataset configuration with appropriate access rules
3. Apply Terraform changes: `terraform apply`

### Adding New Tables
1. Create YAML files in `terraform/bigquery_tables/<dataset_name>/`
2. Define schema, partitioning, and clustering
3. Apply Terraform changes

### Adding Transfer Jobs
1. Configure in `terraform/transfer_jobs/main.tf`
2. Specify S3 source and BigQuery destination
3. Set schedule and authentication