# Airflow Infrastructure

This module creates and manages a complete Apache Airflow orchestration platform on Google Cloud Platform with automated DAG synchronization, robust connection management, and seamless Jenkins CI/CD integration.

## 🏗️ Architecture Overview

The Airflow infrastructure is designed as a production-ready orchestration platform:

- **Compute**: Debian 11 VM with optimized Docker containerization
- **Services**: Multi-container Airflow deployment (webserver, scheduler, PostgreSQL)
- **Storage**: GCS bucket integration for DAG files, logs, and configuration
- **Networking**: Secure VM networking with external IP for web access
- **Automation**: Comprehensive startup scripts and health monitoring
- **CI/CD**: Seamless Jenkins pipeline integration with intelligent deployment

### Infrastructure Components

```
🏗️ Infrastructure Stack
├── 🖥️  Compute Engine VM (airflow-vm)
│   ├── 🐧 Debian 11 base image
│   ├── 🐳 Docker & Docker Compose
│   └── 🔧 Automated startup scripts
├── 🗄️  PostgreSQL Database
│   ├── 📊 Airflow metadata storage
│   └── 🔒 Local container deployment
├── 🌐 Airflow Services
│   ├── 🖥️  Webserver (Port 8081)
│   ├── ⚡ Scheduler (background)
│   └── 👤 Admin user management
├── ☁️  GCS Integration
│   ├── 📁 DAG file synchronization
│   ├── 📝 Log file storage
│   └── 🔧 Configuration management
└── 🔐 Security Layer
    ├── 🔑 Service account authentication
    ├── 🛡️  IAM role management
    └── 🔒 Secret management
```

## 🔗 Jenkins CI/CD Integration

### Pipeline Architecture

The module is tightly integrated with the Jenkins pipeline for automated deployments:

```
Jenkins Pipeline Flow:
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Code Changes   │───▶│   DAG Detection  │───▶│   GCS Upload    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Terraform Init  │───▶│  VM Health Check │───▶│ Smart Planning  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Infrastructure  │───▶│ Connection Setup │───▶│   Validation    │
│    Deployment   │    │   & Variables    │    │   & Testing     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Smart VM Management

The pipeline implements intelligent VM lifecycle management:

#### Scenario 1: Healthy VM (Skip Recreation)
```groovy
// Pipeline detects healthy VM
env.SKIP_VM_RECREATION = 'true'

// Benefits:
✅ Faster deployment (30s vs 5+ minutes)
✅ Zero downtime for running DAGs
✅ Preserves VM customizations
✅ Reduces GCP compute costs
```

#### Scenario 2: New/Unhealthy VM (Full Recreation)
```groovy
// Pipeline detects VM needs recreation
env.SKIP_VM_RECREATION = 'false'

// Process:
🔄 Terraform creates new VM
⏳ Wait for Docker containers (3+ minutes)  
🏥 Health check until Airflow responds
✅ Proceed with configuration
```

### Pipeline Stages Integration

Each pipeline stage has specific Airflow integration:

1. **DAG Change Detection**: Only uploads DAGs when actual changes detected
2. **VM Health Assessment**: Determines optimal deployment strategy
3. **Targeted Planning**: Avoids unnecessary VM recreation
4. **Automated Connections**: Post-deployment connection setup
5. **Health Validation**: Ensures Airflow is ready before completion

## 🎯 Production Features

### High Availability Design
- **Health Monitoring**: Continuous health checks via `/health` endpoint
- **Auto-Recovery**: Automatic restart on container failures
- **Persistent Storage**: Data survives VM restarts
- **Backup Strategy**: GCS-based configuration backup

### Performance Optimization
- **Resource Allocation**: Optimized CPU and memory for VM
- **Container Efficiency**: Minimal container resource usage
- **Database Performance**: Tuned PostgreSQL configuration
- **Network Optimization**: Efficient GCS synchronization

### Security Implementation
- **Service Account Isolation**: Dedicated SA with minimal permissions
- **Network Security**: Controlled firewall rules
- **Secret Management**: Secure credential handling
- **Access Control**: Role-based access to Airflow UI

## 🔧 DAG Development Workflow

### Local Development
```bash
# 1. Develop DAGs locally
mkdir -p local_dags
# ... develop your DAG files ...

# 2. Test DAG syntax
python -m py_compile your_dag.py

# 3. Upload to GCS (via scripts)
cd ../../scripts
./upload_config.sh
```

### CI/CD Integration
```bash
# Automatic workflow via Jenkins:
# 1. Commit changes to Git
# 2. Jenkins detects DAG changes
# 3. Pipeline uploads to GCS automatically
# 4. VM syncs DAGs within minutes
# 5. Airflow picks up new DAGs
```

### DAG Best Practices
```python
# Example DAG structure for this infrastructure
from airflow import DAG
from airflow.providers.google.cloud.operators.bigquery import BigQueryCreateEmptyTableOperator
from airflow.models import Variable
from datetime import datetime, timedelta

# Use Airflow Variables for configuration
PROJECT_ID = Variable.get("gcp_project_id")
DATASET_ID = Variable.get("tpe_mrt_bronze_dataset_id")

default_args = {
    'owner': 'data-team',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG(
    'tpe_mrt_processing',
    default_args=default_args,
    description='Process TPE MRT data',
    schedule_interval=timedelta(hours=1),
    catchup=False,
    tags=['bigquery', 'mrt', 'bronze'],
)
```

## 🚀 Deployment Scenarios

### Scenario 1: New Infrastructure Deployment
```bash
# Full deployment from scratch
cd terraform
terraform init
terraform plan  # Review all resources
terraform apply # Creates everything

# Expected timeline:
⏱️ VM Creation: 2-3 minutes
⏱️ Container Startup: 3-5 minutes
⏱️ Health Check: 1-2 minutes
⏱️ Connection Setup: 1 minute
📊 Total: ~10 minutes
```

### Scenario 2: DAG-Only Updates
```bash
# Via Jenkins pipeline (automatic)
# OR manual via scripts:
cd scripts
./upload_config.sh

# Expected timeline:
⏱️ GCS Upload: 30 seconds
⏱️ VM Sync: 1-2 minutes
⏱️ Airflow Pickup: 1 minute
📊 Total: ~3-4 minutes
```

### Scenario 3: Configuration Updates
```bash
# Via Jenkins pipeline (automatic)
# Infrastructure changes only

# Expected timeline (if VM healthy):
⏱️ Terraform Plan: 1 minute
⏱️ Apply Changes: 2-3 minutes
⏱️ Connection Update: 1 minute
📊 Total: ~5 minutes
```

## 📊 Monitoring and Observability

### Health Endpoints
```bash
# Airflow health check
curl http://<VM_IP>:8081/health

# Expected response:
{
  "metadatabase": {"status": "healthy"},
  "scheduler": {"status": "healthy"}
}
```

### Log Management
```bash
# Container logs
docker-compose logs airflow-webserver
docker-compose logs airflow-scheduler

# System logs
sudo journalctl -u docker
sudo journalctl -f  # Follow logs
```

### Performance Monitoring
```bash
# Resource usage
docker stats

# VM metrics
gcloud compute instances describe airflow-vm \
  --zone=asia-east1-b \
  --format="table(name,status,machineType,disks[0].diskSizeGb)"
```

## 🛠️ Advanced Configuration

### Custom Airflow Configuration
The module supports custom Airflow configurations via template files:

```bash
# Edit Airflow configuration
nano templates/airflow.cfg.tpl

# Key settings for this infrastructure:
[core]
executor = LocalExecutor
sql_alchemy_conn = postgresql+psycopg2://airflow:airflow@postgres/airflow
load_examples = False

[webserver]
base_url = http://<VM_IP>:8081
web_server_port = 8081

[scheduler]
job_heartbeat_sec = 5
scheduler_heartbeat_sec = 5
```

### Environment Variables
Critical environment variables used by the infrastructure:

```bash
# Terraform variables
TF_VAR_project_id         # GCP project ID
TF_VAR_region            # GCP region
TF_VAR_zone              # GCP zone

# Pipeline variables  
GOOGLE_APPLICATION_CREDENTIALS  # Service account key
AIRFLOW_BUCKET                 # GCS bucket name
SKIP_VM_RECREATION            # Smart deployment flag
```

### Resource Scaling
```hcl
# Adjust VM resources in main.tf
resource "google_compute_instance" "airflow" {
  machine_type = "e2-standard-2"  # Increase for higher workloads
  
  boot_disk {
    initialize_params {
      size = 50  # Increase disk size if needed
    }
  }
}
```

## 🔍 Troubleshooting Guide

### Common Deployment Issues

**Issue**: VM creation timeout
```bash
# Check VM status
gcloud compute instances describe airflow-vm --zone=asia-east1-b

# Solution: Verify quotas and permissions
gcloud compute project-info describe --project=open-data-v2-cicd
```

**Issue**: Docker containers not starting
```bash
# SSH into VM and check
gcloud compute ssh airflow-vm --zone=asia-east1-b

# Check Docker status
sudo systemctl status docker
docker-compose ps

# Solution: Usually resolves with VM restart
sudo reboot
```

**Issue**: Airflow UI not accessible
```bash
# Check firewall rules
gcloud compute firewall-rules list --filter="name:airflow"

# Check VM external IP
gcloud compute instances describe airflow-vm \
  --zone=asia-east1-b \
  --format="get(networkInterfaces[0].accessConfigs[0].natIP)"
```

**Issue**: Connection setup fails
```bash
# Check service account key
gcloud compute ssh airflow-vm --zone=asia-east1-b
ls -la /opt/airflow/config/service-account.json

# Re-run connection setup
cd /opt/airflow
./airflow-manager.sh connections
```

### Pipeline-Specific Issues

**Issue**: "docker: command not found" in Jenkins
```bash
# Root cause: Pipeline stage runs before VM creation
# Solution: ✅ Fixed in updated pipeline - proper stage ordering
```

**Issue**: Configuration update timeout
```bash
# Root cause: Waiting for unhealthy VM
# Solution: ✅ Smart conditional logic implemented
```

**Issue**: Connection creation fails
```bash
# Root cause: Airflow not ready
# Solution: ✅ Health check integration added
```

## 📚 Related Documentation

- **Main README**: `../../README.md` - Project overview and architecture
- **Terraform README**: `../README.md` - Infrastructure configuration details  
- **Scripts README**: `../../scripts/README.md` - Operational scripts documentation
- **Auto-Connections**: `./README_AUTO_CONNECTIONS.md` - Detailed connection setup guide
- **Jenkins Pipeline**: `../../Jenkinsfile` - Complete CI/CD pipeline configuration

## 🎯 Next Steps and Roadmap

### Immediate Improvements
- [ ] Add Airflow task monitoring and alerting
- [ ] Implement DAG testing framework
- [ ] Add automated backup and restore procedures
- [ ] Enhance security with VPC networking

### Long-term Enhancements  
- [ ] Multi-zone deployment for high availability
- [ ] Kubernetes-based Airflow deployment
- [ ] Integration with Google Cloud Composer
- [ ] Advanced monitoring with Prometheus/Grafana

### Performance Optimizations
- [ ] Implement Airflow task parallelization
- [ ] Add Redis for better task distribution
- [ ] Optimize BigQuery connection pooling
- [ ] Implement smart DAG scheduling

## 🔗 Airflow Connections & Variables Management

### **Architecture Overview**

There are **two complementary systems** for managing Airflow connections and variables:

#### **1. 🤖 Automated System (Long-term/Persistent)**
- **Purpose**: Permanent configuration that survives VM restarts
- **When**: Executed automatically every time VM starts
- **Files**: 
  - `templates/airflow_connections.sh.tpl` - Connection templates
  - `templates/airflow_variables.sh.tpl` - Variable templates
- **Execution Flow**:
  ```
  Terraform → VM Metadata → Startup Script → Template Execution → Airflow Configuration
  ```

#### **2. 🛠️ Manual System (Immediate/Troubleshooting)**
- **Purpose**: Quick fixes, immediate changes, troubleshooting
- **When**: Run manually when needed
- **Tool**: `scripts/airflow-manager.sh connections`
- **Use Case**: "I need to fix this right now"

### **How Template Execution Works**

1. **Terraform** renders templates and stores them in **VM metadata**:
   ```hcl
   metadata = {
     airflow-connections = templatefile("${path.module}/templates/airflow_connections.sh.tpl", {
       project_id = var.project_id
     })
     airflow-variables = templatefile("${path.module}/templates/airflow_variables.sh.tpl", {
       project_id = var.project_id
     })
   }
   ```

2. **VM Startup Script** reads metadata and executes:
   ```bash
   # Get templates from metadata
   CONNECTIONS_SCRIPT=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/attributes/airflow-connections" -H "Metadata-Flavor: Google")
   
   # Execute the templates
   /tmp/create_connections.sh
   /tmp/create_variables.sh
   ```

### **Adding New Connections or Variables**

#### **📝 For Permanent Changes (Recommended)**

**Step 1: Update Template Files**

For **Variables**:
```bash
# Edit the template
nano terraform/airflow/templates/airflow_variables.sh.tpl

# Add your new variables (example):
airflow variables set "my_new_variable" "my_value"
airflow variables set "api_endpoint" "https://api.example.com"
airflow variables set "batch_size" "1000"
```

For **Connections**:
```bash
# Edit the template
nano terraform/airflow/templates/airflow_connections.sh.tpl

# Add your new connections (example):
airflow connections add 'my_postgres_conn' \
    --conn-type 'postgres' \
    --conn-host 'localhost' \
    --conn-login 'myuser' \
    --conn-password 'mypass' \
    --conn-schema 'mydb' \
    --conn-port '5432'
```

**Step 2: Update Airflow Manager Script**
```bash
# Edit the script
nano scripts/airflow-manager.sh

# Find the create_connections() function and add your new items:
docker-compose exec -T airflow-webserver airflow variables set "my_new_variable" "my_value"
echo "✅ Set my_new_variable"
```

**Step 3: Apply Changes**
```bash
# Apply Terraform changes (updates VM metadata)
cd terraform
terraform apply

# For immediate effect, also run:
cd ../scripts
./airflow-manager.sh connections
```

#### **⚡ For Immediate Changes (Quick Fix)**

```bash
# Just run the manual command
cd scripts
./airflow-manager.sh connections

# This will create all connections and variables immediately
```

### **Current Configuration**

#### **🔗 Connections**
- `google_cloud_default`: Google Cloud Platform connection
  - Type: `google_cloud_platform`
  - Project: `open-data-v2-cicd`
  - Key Path: `/opt/airflow/config/service-account.json`

#### **�� Variables**
- `gcp_project_id`: `open-data-v2-cicd`
- `project_id`: `open-data-v2-cicd`
- `bigquery_location`: `asia-east1` (Taiwan region)
- `notification_email`: `["admin@example.com"]`
- `environment`: `dev`
- `data_retention_days`: `30`
- `max_parallel_tasks`: `5`

**Dataset Variables (used in SQL queries)**:
- `tpe_mrt_bronze_dataset_id`: `tpe_mrt_bronze`
- `tpe_mrt_silver_dataset_id`: `tpe_mrt_silver`
- `tpe_mrt_gold_dataset_id`: `tpe_mrt_gold`

### **Verification Steps**

After adding new connections/variables:

1. **Check in Airflow UI**:
   - Navigate to `http://<VM_IP>:8081`
   - Admin → Connections (verify connections)
   - Admin → Variables (verify variables)

2. **Test in DAGs**:
   ```python
   from airflow.models import Variable
   from airflow.hooks.base import BaseHook
   
   # Test variable
   my_var = Variable.get("my_new_variable")
   
   # Test connection
   conn = BaseHook.get_connection("my_postgres_conn")
   ```

3. **Verify via Script**:
   ```bash
   cd scripts
   ./airflow-manager.sh connections  # Shows verification output
   ```

### **Common Connection Types**

#### **Google Cloud Platform**
```bash
airflow connections add 'my_gcp_conn' \
    --conn-type 'google_cloud_platform' \
    --conn-extra '{"project": "my-project", "key_path": "/path/to/key.json"}'
```

#### **PostgreSQL**
```bash
airflow connections add 'my_postgres_conn' \
    --conn-type 'postgres' \
    --conn-host 'localhost' \
    --conn-login 'user' \
    --conn-password 'pass' \
    --conn-schema 'db' \
    --conn-port '5432'
```

#### **HTTP/API**
```bash
airflow connections add 'my_api_conn' \
    --conn-type 'http' \
    --conn-host 'api.example.com' \
    --conn-extra '{"timeout": 30}'
```

### **Best Practices**

1. **Always use templates** for permanent changes
2. **Test changes manually first** with `airflow-manager.sh`
3. **Use descriptive variable names** with prefixes (`gcp_`, `api_`, etc.)
4. **Document your variables** in this README
5. **Keep sensitive data in Google Secret Manager**, not in variables
6. **Restart VM after template changes** to ensure they take effect

## 👥 User Management

### User Structure
- **System User**: `airflow` (UID 997) - for host operations
- **Container User**: `airflow-container` (UID 50000) - for Docker containers
- **Docker Containers**: Run as UID 50000 for security and consistency

### Permission System
- All Airflow directories (`/opt/airflow/{dags,logs,config,plugins}`) are owned by UID 50000
- GCS sync service runs as `airflow-container` user
- Automatic permission fix service runs on every boot
- Startup script ensures correct permissions on VM creation/restart

## 🔧 Permanent Fixes Applied

### 1. Terraform Configuration
- Removed `metadata_startup_script` from `ignore_changes` to allow startup script updates
- Enhanced startup script with robust permission handling

### 2. Boot-time Permission Service
A systemd service (`airflow-permissions.service`) automatically fixes permissions on every boot:
```bash
# Service runs: chown -R 50000:0 /opt/airflow/{dags,logs,plugins,config}
sudo systemctl status airflow-permissions.service
```

### 3. GCS Sync Service
Properly configured to run as `airflow-container` user:
```bash
sudo systemctl status gcs-sync.service
```

## 🚀 Deployment

### Initial Deployment
```bash
cd terraform
terraform init
terraform plan -var="project_id=your-project" -var="aws_access_key=xxx" -var="aws_secret_key=xxx" -var="s3_bucket=xxx"
terraform apply
```

### DAG Updates
```bash
cd scripts
./upload_config.sh  # Syncs DAGs to GCS, automatically pulled by VM
```

### Permission Fixes (if needed)
```bash
cd scripts
./fix_airflow_permissions.sh  # Comprehensive fix for current VM
```

## 🔍 Monitoring & Validation

### Health Check
```bash
cd scripts
./validate_airflow.sh
```

### Manual Checks
```bash
# Check services
gcloud compute ssh airflow-vm --zone=asia-east1-b --command='cd /opt/airflow && sudo docker-compose ps'

# Check permissions
gcloud compute ssh airflow-vm --zone=asia-east1-b --command='ls -la /opt/airflow/'

# Check logs
gcloud compute ssh airflow-vm --zone=asia-east1-b --command='cd /opt/airflow && sudo docker-compose logs airflow-scheduler --tail=20'
```

## 🔄 VM Lifecycle

### Restart VM
```bash
cd scripts
./restart_airflow_vm.sh  # Safe restart with health monitoring
```

### Recreate VM
```bash
cd terraform
terraform destroy -target=module.airflow.google_compute_instance.airflow
terraform apply  # Startup script will configure everything correctly
```

## 🛠️ Troubleshooting

### DAGs Not Showing
1. Check GCS sync: `sudo systemctl status gcs-sync.service`
2. Check permissions: `ls -la /opt/airflow/dags/`
3. Check scheduler logs: `sudo docker-compose logs airflow-scheduler`
4. Run permission fix: `./scripts/fix_airflow_permissions.sh`

### Permission Issues
1. Check user existence: `getent passwd | grep -E "(airflow|50000)"`
2. Check directory ownership: `ls -la /opt/airflow/`
3. Run comprehensive fix: `./scripts/fix_airflow_permissions.sh`

### Service Issues
1. Check all services: `sudo docker-compose ps`
2. Restart services: `sudo docker-compose restart`
3. Check startup logs: `sudo journalctl -u google-startup-scripts.service`

## 📋 Access Information

- **Web UI**: `http://<VM_IP>:8081`
- **Username**: `admin`
- **Password**: `admin`
- **VM SSH**: `gcloud compute ssh airflow-vm --zone=asia-east1-b`

## 🔐 Security Notes

- VM uses service account with minimal required permissions
- Airflow containers run as non-root user (UID 50000)
- GCS bucket has versioning and lifecycle policies
- Firewall rules restrict access to necessary ports only

## 🎯 Persistence Guarantees

This configuration ensures permissions and setup persist through:
- ✅ VM restarts (boot-time permission service)
- ✅ VM recreations (enhanced startup script)
- ✅ Terraform updates (startup script updates allowed)
- ✅ Manual interventions (comprehensive fix script available)

## File Structure

```
terraform/airflow/
├── main.tf                     # Main infrastructure resources
├── variables.tf                # Input variables
├── outputs.tf                  # Output values
├── templates/
│   └── startup_script.sh.tpl   # VM startup script template
└── docker/
    ├── docker-compose.yml      # Docker services configuration
    ├── Dockerfile              # Custom Airflow image
    ├── requirements.txt        # Python dependencies
    ├── config/
    │   └── airflow.cfg         # Airflow configuration
    └── dags/
        └── example_dag.py      # Example DAG
```

## Deployment

1. **Initialize Terraform**:
   ```bash
   cd terraform
   terraform init
   ```

2. **Plan deployment**:
   ```bash
   terraform plan -var="project_id=your-project-id"
   ```

3. **Apply configuration**:
   ```bash
   terraform apply -var="project_id=your-project-id"
   ```

## Common Issues and Troubleshooting

### Issue 1: Airflow UI Not Accessible

**Symptoms**: Cannot access `http://<VM_IP>:8081`

**Diagnosis**:
```bash
# Check VM status
gcloud compute instances list --filter="name=airflow-vm"

# Check services on VM
gcloud compute ssh airflow-vm --zone=asia-east1-b --command="
  cd /opt/airflow && 
  sudo docker-compose ps &&
  sudo netstat -tlnp | grep :8081
"
```

**Common Causes & Solutions**:

1. **Permission Issues** (Most Common):
   ```bash
   # Fix permissions
   gcloud compute ssh airflow-vm --zone=asia-east1-b --command="
     cd /opt/airflow &&
     sudo chown -R 50000:0 /opt/airflow/logs /opt/airflow/dags /opt/airflow/plugins /opt/airflow/config &&
     sudo chmod -R 755 /opt/airflow/logs &&
     sudo docker-compose restart
   "
   ```

2. **Services Not Started**:
   ```bash
   # Restart services
   gcloud compute ssh airflow-vm --zone=asia-east1-b --command="
     cd /opt/airflow &&
     sudo docker-compose down &&
     sudo docker-compose up -d
   "
   ```

3. **Database Issues**:
   ```bash
   # Check and reinitialize database
   gcloud compute ssh airflow-vm --zone=asia-east1-b --command="
     cd /opt/airflow &&
     sudo docker-compose run --rm airflow-init
   "
   ```

### Issue 2: Admin User Not Created

**Solution**:
```bash
# Create admin user manually
gcloud compute ssh airflow-vm --zone=asia-east1-b --command="
  cd /opt/airflow &&
  sudo docker-compose exec airflow-webserver airflow users create \
    --username admin \
    --password admin \
    --firstname Airflow \
    --lastname Admin \
    --role Admin \
    --email admin@example.com
"
```

### Issue 3: DAGs Not Appearing

**Diagnosis**:
```bash
# Check GCS sync service
gcloud compute ssh airflow-vm --zone=asia-east1-b --command="
  sudo systemctl status gcs-sync.service &&
  ls -la /opt/airflow/dags/
"
```

**Solution**:
```bash
# Restart GCS sync and check DAGs
gcloud compute ssh airflow-vm --zone=asia-east1-b --command="
  sudo systemctl restart gcs-sync.service &&
  sudo docker-compose restart airflow-scheduler
"
```

### Issue 4: Startup Script Failures

**Check startup logs**:
```bash
gcloud compute ssh airflow-vm --zone=asia-east1-b --command="
  sudo journalctl -u google-startup-scripts.service --no-pager | tail -100
"
```

## Monitoring and Logs

### Check Service Status
```bash
# All services
gcloud compute ssh airflow-vm --zone=asia-east1-b --command="
  cd /opt/airflow && sudo docker-compose ps
"

# Specific service logs
gcloud compute ssh airflow-vm --zone=asia-east1-b --command="
  cd /opt/airflow && sudo docker-compose logs airflow-webserver --tail=50
"
```

### Health Check
```bash
# Test health endpoint
curl http://<VM_IP>:8081/health
```

## Maintenance

### Updating DAGs
DAGs are automatically synced from GCS. To update:
1. Upload new DAGs to `gs://<bucket>/docker/dags/`
2. Wait for GCS sync service to pull changes (runs every 60 seconds)

### Updating Configuration
1. Update files in `terraform/airflow/docker/`
2. Upload to GCS: `gsutil cp -r terraform/airflow/docker/* gs://<bucket>/docker/`
3. Restart VM or services

### Manual VM Control
```bash
# Start VM
gcloud compute instances start airflow-vm --zone=asia-east1-b

# Stop VM
gcloud compute instances stop airflow-vm --zone=asia-east1-b
```

## Security Considerations

- VM uses service account with minimal required permissions
- Firewall rule restricts access to port 8081 only
- Service account keys stored in Secret Manager
- Default admin credentials should be changed in production

## Cost Optimization

- VM automatically stops on Sunday midnight (Taiwan Time)
- VM automatically starts on Saturday 8:00 AM (Taiwan Time)
- Preemptible instances not used to ensure reliability
- Storage lifecycle policies delete old logs after 30 days

## Troubleshooting Checklist

When Airflow is not working:

1. ✅ **VM Running**: `gcloud compute instances list --filter="name=airflow-vm"`
2. ✅ **Port Accessible**: `curl http://<VM_IP>:8081/health`
3. ✅ **Services Running**: Check `docker-compose ps` on VM
4. ✅ **Permissions Correct**: Ensure UID 50000 owns `/opt/airflow/logs`
5. ✅ **Database Healthy**: Check PostgreSQL container status
6. ✅ **Admin User Exists**: Try logging in with admin/admin
7. ✅ **DAGs Synced**: Check `/opt/airflow/dags/` directory

## Support

For issues not covered in this guide:
1. Check startup script logs: `journalctl -u google-startup-scripts.service`
2. Check Docker logs: `docker-compose logs <service-name>`
3. Verify GCS bucket contents and permissions
4. Ensure Secret Manager contains service account key 