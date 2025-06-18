# Airflow Auto-Connections Setup

This document explains the automated connection and variable management system that integrates seamlessly with both VM lifecycle and Jenkins CI/CD pipeline.

## 🎯 Overview

The auto-connections system ensures Airflow connections and variables are automatically configured and maintained across different deployment scenarios, providing zero-touch operations for both developers and operators.

## 🏗️ Architecture Integration

### System Components
```
🔄 Auto-Connection Architecture
├── 🤖 Template System (Persistent)
│   ├── 📄 airflow_connections.sh.tpl
│   ├── 📄 airflow_variables.sh.tpl  
│   └── 🔧 VM metadata integration
├── 🚀 Jenkins Pipeline (Automated)
│   ├── 📊 Connection verification
│   ├── ⚡ Smart conditional execution
│   └── 🔄 Fallback mechanisms
├── 🛠️ Manual Tools (Immediate)
│   ├── 📜 airflow-manager.sh
│   ├── 🔧 Direct connection management
│   └── 🆘 Emergency procedures
└── 🔧 Systemd Service (VM-level)
    ├── 🏥 Health check integration
    ├── ⏰ Startup automation
    └── 📝 Comprehensive logging
```

## 🔄 Jenkins Pipeline Integration

### Pipeline Stage: "Setup Airflow Connections & Variables"

The Jenkins pipeline includes a dedicated stage for connection management:

```groovy
stage('Setup Airflow Connections & Variables') {
    steps {
        script {
            echo "=== Setting up Airflow Connections & Variables ==="
            
            // Smart conditional execution based on VM state
            if (env.SKIP_VM_RECREATION == 'true') {
                echo "✅ VM was already running, minimal setup required"
                sleep(time: 30, unit: 'SECONDS')
            } else {
                echo "🔄 VM was created/recreated, waiting for full readiness..."
                sleep(time: 180, unit: 'SECONDS')
                
                // Health monitoring with timeout
                timeout(time: 10, unit: 'MINUTES') {
                    waitUntil {
                        script {
                            def healthCheck = sh(
                                script: "curl -s -o /dev/null -w '%{http_code}' http://${vmIp}:8081/health",
                                returnStdout: true
                            ).trim()
                            return healthCheck == '200'
                        }
                    }
                }
            }
            
            // Execute connection setup
            sh '''
                cd scripts
                chmod +x airflow-manager.sh
                ./airflow-manager.sh connections
            '''
        }
    }
}
```

### Pipeline Benefits

**Automated Deployment**: No manual intervention required
**Smart Execution**: Adapts to VM state (new vs existing)
**Health Validation**: Ensures Airflow is ready before proceeding
**Error Handling**: Robust fallback mechanisms
**Consistent State**: Guarantees connections exist after deployment

## 🎯 Deployment Scenarios

### Scenario 1: New Infrastructure Deployment
```bash
# Jenkins Pipeline Flow:
📦 Terraform Apply → 🆕 VM Creation → ⏳ Startup Wait → 🔗 Connection Setup → ✅ Ready

# Timeline:
⏱️ VM Creation: 2-3 minutes
⏱️ Docker Startup: 3-5 minutes  
⏱️ Health Check: 1-2 minutes
⏱️ Connection Setup: 1 minute
📊 Total: ~10 minutes
```

### Scenario 2: Existing VM (Healthy)
```bash
# Jenkins Pipeline Flow:
📦 Terraform Apply → 🏥 Health Check → ⚡ Quick Setup → ✅ Ready

# Timeline:
⏱️ Health Check: 30 seconds
⏱️ Connection Setup: 30 seconds
📊 Total: ~1 minute
```

### Scenario 3: VM Restart/Recovery
```bash
# Systemd Service Activation:
🔄 VM Startup → 🏥 Airflow Health Check → 🔗 Auto-Connection → ✅ Ready

# Timeline:
⏱️ Boot Process: 1-2 minutes
⏱️ Airflow Startup: 2-3 minutes
⏱️ Connection Setup: 30 seconds
📊 Total: ~4-5 minutes
```

## 🔧 Dual Management Systems

### 1. 🤖 Template-Based System (Persistent)

**Purpose**: Long-term, infrastructure-level configuration
**Execution**: Automatic on every VM startup via systemd
**Files**: VM metadata stores rendered templates

```hcl
# Terraform integration
metadata = {
  airflow-connections = templatefile("${path.module}/templates/airflow_connections.sh.tpl", {
    project_id = var.project_id
    # ... other variables
  })
  airflow-variables = templatefile("${path.module}/templates/airflow_variables.sh.tpl", {
    project_id = var.project_id
    # ... other variables  
  })
}
```

**Benefits**:
- ✅ Survives VM restarts and recreations
- ✅ Version-controlled via Terraform
- ✅ Consistent across deployments
- ✅ No manual intervention required

### 2. 🛠️ Script-Based System (Immediate)

**Purpose**: Immediate fixes, testing, and troubleshooting
**Execution**: Manual via `airflow-manager.sh connections`
**Location**: `../../scripts/airflow-manager.sh`

```bash
# Quick connection setup
cd scripts
./airflow-manager.sh connections

# Check existing connections
./airflow-manager.sh validate
```

**Benefits**:
- ✅ Immediate execution
- ✅ Troubleshooting friendly
- ✅ Development workflow support
- ✅ Emergency repair capabilities

## 🔗 Connection & Variable Configuration

### Current Connections

**Google Cloud Platform Connection**
```bash
# Connection ID: google_cloud_default
# Type: google_cloud_platform  
# Project: open-data-v2-cicd
# Key Path: /opt/airflow/config/service-account.json
# Scopes: https://www.googleapis.com/auth/cloud-platform
```

### Current Variables

**Core Configuration**
- `gcp_project_id`: `open-data-v2-cicd`
- `project_id`: `open-data-v2-cicd`  
- `bigquery_location`: `asia-east1`
- `environment`: `dev`

**Operational Settings**
- `notification_email`: `["admin@example.com"]`
- `data_retention_days`: `30`
- `max_parallel_tasks`: `5`
- `airflow_bucket`: `open-data-v2-cicd-airflow-storage`

**Dataset References**
- `tpe_mrt_bronze_dataset_id`: `tpe_mrt_bronze`
- `tpe_mrt_silver_dataset_id`: `tpe_mrt_silver`
- `tpe_mrt_gold_dataset_id`: `tpe_mrt_gold`

## 🚀 Adding New Connections or Variables

### Method 1: Template-Based (Recommended for Production)

**Step 1: Update Templates**
```bash
# For connections
nano terraform/airflow/templates/airflow_connections.sh.tpl

# Add new connection
airflow connections add 'my_new_connection' \
    --conn-type 'postgres' \
    --conn-host 'localhost' \
    --conn-login 'user' \
    --conn-password 'pass' \
    --conn-schema 'mydb' \
    --conn-port '5432'
```

```bash
# For variables  
nano terraform/airflow/templates/airflow_variables.sh.tpl

# Add new variable
airflow variables set "my_new_variable" "my_value"
```

**Step 2: Update Script (for immediate effect)**
```bash
# Update airflow-manager.sh
nano scripts/airflow-manager.sh

# Add to create_connections function
docker-compose exec -T airflow-webserver airflow connections add 'my_new_connection' \
    --conn-type 'postgres' \
    --conn-host 'localhost' \
    --conn-login 'user' \
    --conn-password 'pass'
```

**Step 3: Deploy Changes**
```bash
# Via Terraform (updates templates)
cd terraform
terraform apply

# Via Jenkins Pipeline (automatic)
# OR immediate via script
cd scripts
./airflow-manager.sh connections
```

### Method 2: Script-Only (Development/Testing)

```bash
# Quick addition for development
cd scripts
./airflow-manager.sh connections

# Manual validation
./airflow-manager.sh validate
```

## 🔍 Verification and Testing

### Automated Verification (Pipeline)
```bash
# Pipeline includes automatic verification
# Check Jenkins logs for:
echo "✅ Connections verified successfully"
echo "✅ Variables configured correctly"
```

### Manual Verification
```bash
# Access Airflow UI
open http://<VM_IP>:8081

# Navigate to:
# Admin → Connections (verify connections)
# Admin → Variables (verify variables)
```

### Script-Based Verification
```bash
# Comprehensive check
cd scripts
./airflow-manager.sh validate

# Connection-specific check
./airflow-manager.sh check-connections
```

### DAG-Level Testing
```python
# Test in your DAGs
from airflow.models import Variable
from airflow.hooks.base import BaseHook

def test_connections_and_variables():
    # Test variable access
    project_id = Variable.get("gcp_project_id")
    assert project_id == "open-data-v2-cicd"
    
    # Test connection access
    conn = BaseHook.get_connection("google_cloud_default")
    assert conn.conn_type == "google_cloud_platform"
```

## 🔧 Systemd Service Details

### Service Configuration
```ini
# /etc/systemd/system/airflow-connections.service
[Unit]
Description=Airflow Connections Auto-Setup
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
User=root
ExecStart=/opt/airflow/setup-connections.sh
Restart=no
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

### Service Management
```bash
# Check service status
sudo systemctl status airflow-connections.service

# View service logs
sudo journalctl -u airflow-connections.service -f

# Manual service execution
sudo systemctl start airflow-connections.service

# Disable service (if needed)
sudo systemctl disable airflow-connections.service
```

## 🛠️ Troubleshooting Guide

### Common Issues

**Issue**: Connections not created after VM restart
```bash
# Check systemd service
sudo systemctl status airflow-connections.service

# Check service logs
sudo journalctl -u airflow-connections.service

# Manual execution
sudo systemctl start airflow-connections.service
```

**Issue**: Pipeline connection setup fails
```bash
# Check Airflow health
curl http://<VM_IP>:8081/health

# Check VM Docker status
gcloud compute ssh airflow-vm --zone=asia-east1-b --command='docker ps'

# Re-run connection setup
cd scripts
./airflow-manager.sh connections
```

**Issue**: Variables not appearing in Airflow UI
```bash
# Check Airflow logs
docker-compose logs airflow-webserver

# Manual variable creation
cd scripts
./airflow-manager.sh connections

# Verify in UI
open http://<VM_IP>:8081/admin/variable/
```

### Emergency Procedures

**Complete Connection Reset**
```bash
# 1. Clear existing connections
cd scripts
./airflow-manager.sh emergency-fix

# 2. Recreate all connections
./airflow-manager.sh connections

# 3. Verify setup
./airflow-manager.sh validate
```

**Pipeline Failure Recovery**
```bash
# 1. Check VM status
gcloud compute instances describe airflow-vm --zone=asia-east1-b

# 2. Manual connection setup
cd scripts
./airflow-manager.sh connections

# 3. Re-run pipeline stage
# (Manual trigger in Jenkins)
```

## 📊 Monitoring and Logging

### Connection Setup Logs
```bash
# Systemd service logs
sudo journalctl -u airflow-connections.service

# Startup script logs
sudo tail -f /var/log/airflow-connections.log

# Pipeline logs
# Check Jenkins pipeline console output
```

### Health Monitoring
```bash
# Check connection health
cd scripts
./airflow-manager.sh validate

# Check Airflow health
curl http://<VM_IP>:8081/health

# Monitor variables
curl -u admin:admin http://<VM_IP>:8081/api/v1/variables
```

## 🎯 Best Practices

### Development
1. **Test locally**: Use script-based approach for development
2. **Template updates**: Always update templates for production changes
3. **Version control**: All template changes should be committed
4. **Documentation**: Update this README when adding new connections

### Operations
1. **Use pipeline**: Let Jenkins handle connection setup automatically
2. **Monitor logs**: Check service logs for any failures
3. **Verify after deployment**: Always validate connections post-deployment
4. **Emergency procedures**: Know how to manually fix connection issues

### Security
1. **Secret management**: Use secure methods for storing sensitive connection data
2. **Access control**: Limit who can modify connection templates
3. **Audit logging**: Monitor connection creation and modifications
4. **Regular rotation**: Periodically rotate connection credentials

---

## 📚 Related Documentation

- **Main Airflow README**: `./README.md` - Complete Airflow infrastructure guide
- **Scripts README**: `../../scripts/README.md` - Operational scripts documentation  
- **Jenkins Pipeline**: `../../Jenkinsfile` - CI/CD pipeline configuration
- **Terraform Main**: `../README.md` - Infrastructure configuration guide 