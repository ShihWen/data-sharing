# Airflow Infrastructure

This module creates and manages an Airflow instance on Google Cloud Platform with automated DAG synchronization and proper permission management.

## 🏗️ Architecture

- **VM**: Debian 11 with Docker and Docker Compose
- **Services**: Airflow webserver, scheduler, and PostgreSQL database
- **Storage**: GCS bucket for DAG files and logs
- **Sync**: Automated DAG synchronization from GCS
- **Permissions**: Robust user and permission management

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