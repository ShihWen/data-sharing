# Airflow Management Scripts

This directory contains comprehensive scripts for managing the Airflow infrastructure and addressing common operational challenges.

## 🛠️ Available Scripts

### Core Management Scripts

#### `airflow-manager.sh` - Master Management Tool
**Primary tool for all Airflow operations**

```bash
# Available commands
./airflow-manager.sh validate       # Health check and validation
./airflow-manager.sh restart        # Safe VM restart with automatic fixes
./airflow-manager.sh fix            # Apply permanent fixes for persistence
./airflow-manager.sh emergency-fix  # Comprehensive emergency repairs
./airflow-manager.sh connections    # Create connections and variables
./airflow-manager.sh upload         # Upload DAGs to GCS
./airflow-manager.sh status         # Show current status
```

**Key Features:**
- ✅ **Auto-fix on restart**: Automatically applies emergency fixes if validation fails
- ✅ **Comprehensive error handling**: Handles various failure scenarios
- ✅ **Connection & Variable management**: Creates all required Airflow configurations
- ✅ **Health monitoring**: Validates all components before completing operations

#### `update_airflow_config.sh` - Configuration Updates
**Updated with robust error handling for Jenkins pipeline integration**

```bash
./update_airflow_config.sh scheduler terraform/airflow/docker/config/airflow.cfg
./update_airflow_config.sh webserver terraform/airflow/docker/config/airflow.cfg
./update_airflow_config.sh worker terraform/airflow/docker/config/airflow.cfg
```

**New Features (v2.0):**
- ✅ **Docker availability checking**: Waits for Docker to be ready
- ✅ **Container readiness verification**: Ensures Airflow containers are running
- ✅ **Improved error messages**: Clear status indicators and troubleshooting info
- ✅ **Timeout handling**: Prevents indefinite waiting
- ✅ **Jenkins pipeline compatibility**: Works correctly with CI/CD automation

### Utility Scripts

#### `upload_config.sh` - DAG Synchronization
```bash
./upload_config.sh
```
Syncs DAG files from local to GCS bucket for automatic VM pickup.

#### `ensure_permanent_fixes.sh` - Persistence Guarantees
```bash
./ensure_permanent_fixes.sh
```
Ensures all fixes persist through VM restarts and recreations.

#### `setup_auto_connections.sh` - Automatic Connection Setup
```bash
./setup_auto_connections.sh
```
Sets up a systemd service on the Airflow VM to automatically create connections and variables on every VM restart, ensuring a consistent environment. It uses `airflow-manager.sh` to perform the actual configuration.

#### `test-connection-check.sh` - Connection Check Demonstration
```bash
./test-connection-check.sh
```
A test script that demonstrates the time savings of checking for existing Airflow connections before attempting to create them. It is intended for demonstration purposes.

## 🔧 Jenkins Pipeline Integration

### **Fixed Pipeline Order**
The Jenkins pipeline has been updated to fix the "docker: command not found" error:

**Previous (Broken) Order:**
```
1. Checkout Code
2. Upload DAGs to GCS  
3. Update Scheduler Configuration  ← Failed here (VM doesn't exist)
4. Setup Environment
5. Terraform Apply  ← VM created here
```

**Fixed Order:**
```
1. Checkout Code
2. Upload DAGs to GCS
3. Setup Environment
4. Terraform Apply  ← VM created/updated here
5. Update Scheduler Configuration  ← Smart conditional execution
6. Setup Airflow Connections & Variables  ← Always runs after config
```

### **New Pipeline Features**

#### **Smart Conditional Logic**
Pipeline intelligently handles different VM states:

**Case 1: VM Already Running & Healthy** (`SKIP_VM_RECREATION = 'true'`)
```groovy
// Terraform skips VM recreation
// Minimal wait (30 seconds) then proceed with config update
if (env.SKIP_VM_RECREATION == 'true') {
    echo "✅ VM was already running, proceeding with config update..."
    sleep(time: 30, unit: 'SECONDS')
}
```

**Case 2: VM Created/Recreated** (`SKIP_VM_RECREATION = 'false'`)
```groovy
// Terraform creates new VM
// Wait for full startup (3+ minutes) then health check
else {
    echo "🔄 VM was created/recreated, waiting for full readiness..."
    sleep(time: 180, unit: 'SECONDS')
    // + Health monitoring with waitUntil
}
```

#### **Health Monitoring**
Pipeline waits for Airflow to be healthy before proceeding:
```groovy
waitUntil {
    script {
        def healthCheck = sh(script: "curl -s -o /dev/null -w '%{http_code}' http://${vmIp}:8081/health")
        return healthCheck.trim() == '200'
    }
}
```

#### **Automatic Connection Setup**
New pipeline stage automatically creates connections and variables:
```groovy
stage('Setup Airflow Connections & Variables') {
    steps {
        sh './airflow-manager.sh connections'
    }
}
```

## 📋 Troubleshooting Guide

### Common Jenkins Pipeline Issues

#### Issue: "docker: command not found"
**Root Cause**: Pipeline stage runs before VM is created
**Solution**: ✅ Fixed in updated Jenkinsfile - proper stage ordering

#### Issue: "VM not found" 
**Root Cause**: Terraform hasn't created VM yet  
**Solution**: ✅ Removed conditional execution, stages always run after Terraform Apply

#### Issue: "Containers not ready"
**Root Cause**: Docker services still starting up
**Solution**: ✅ Added intelligent wait logic based on VM creation status

#### Issue: "Config update fails on existing VM"
**Root Cause**: Previous logic waited unnecessarily for healthy VMs
**Solution**: ✅ Smart conditional logic - minimal wait for existing VMs, full wait for new VMs

### Manual Troubleshooting

#### Quick Health Check
```bash
cd scripts
./airflow-manager.sh validate
```

#### Fix All Issues
```bash
cd scripts
./airflow-manager.sh restart  # Auto-applies fixes if needed
```

#### Emergency Repair
```bash
cd scripts
./airflow-manager.sh emergency-fix
```

## 🔄 Operational Workflows

### **Development Workflow**
```bash
# 1. Update DAGs locally
# 2. Upload to GCS
cd scripts
./upload_config.sh

# 3. Validate deployment
./airflow-manager.sh validate
```

### **Production Deployment**
```bash
# 1. Run via Jenkins pipeline (automated)
# 2. Verify deployment
cd scripts
./airflow-manager.sh status

# 3. Create connections if needed
./airflow-manager.sh connections
```

### **Incident Response**
```bash
# 1. Quick assessment
cd scripts
./airflow-manager.sh status

# 2. Apply fixes
./airflow-manager.sh emergency-fix

# 3. Full restart if needed
./airflow-manager.sh restart
```

## 🎯 Best Practices

### **For Operations Teams**
1. **Always use `airflow-manager.sh`** for manual operations
2. **Run `validate` first** before making changes
3. **Use `emergency-fix`** only for severe issues
4. **Monitor Jenkins pipeline** for automated deployments

### **For Development Teams**
1. **Test DAGs locally** before uploading
2. **Use `upload_config.sh`** for quick DAG updates
3. **Check Airflow UI** after deployments
4. **Report pipeline failures** to operations team

### **For Jenkins Pipeline**
1. **Let pipeline handle** VM lifecycle
2. **Monitor pipeline logs** for early issue detection
3. **Use conditional stages** to prevent premature execution
4. **Add health checks** before critical operations

## 📚 Script Documentation

### Error Handling Philosophy
All scripts follow a consistent error handling approach:
- ✅ **Fail fast**: Exit immediately on critical errors
- ✅ **Clear messaging**: Descriptive error messages with emojis
- ✅ **Wait strategies**: Intelligent waiting with timeouts
- ✅ **Graceful degradation**: Continue where possible, warn when not

### Configuration Management
Scripts handle configuration in layers:
1. **Template-based**: Persistent configuration via Terraform templates
2. **Script-based**: Manual configuration via airflow-manager
3. **Pipeline-based**: Automated configuration via Jenkins

### Monitoring and Logging
All operations provide:
- 📊 **Status indicators**: Clear success/failure states
- 📝 **Detailed logging**: Step-by-step operation details  
- ⏱️ **Timing information**: Duration and progress tracking
- 🔍 **Debug information**: VM status, container states, etc.

## 🆘 Emergency Procedures

### VM Completely Unresponsive
```bash
# 1. Check VM status
gcloud compute instances describe airflow-vm --zone=asia-east1-b

# 2. Force restart via GCP
gcloud compute instances stop airflow-vm --zone=asia-east1-b
gcloud compute instances start airflow-vm --zone=asia-east1-b

# 3. Apply emergency fix
cd scripts
./airflow-manager.sh emergency-fix
```

### Pipeline Continuously Failing
```bash
# 1. Check VM manually
cd scripts
./airflow-manager.sh status

# 2. Apply comprehensive fix
./airflow-manager.sh fix

# 3. Re-run pipeline
```

### Data Loss/Corruption
```bash
# 1. Check backups in GCS
gsutil ls gs://open-data-v2-cicd-airflow-storage/

# 2. Restore from backup (if available)
# 3. Recreate connections and variables
cd scripts
./airflow-manager.sh connections
```

---

**For additional help**: Check the main Terraform README or consult the Jenkins pipeline logs. 