# Airflow Infrastructure Module

This module provisions an Airflow instance on Google Cloud Platform using Compute Engine and Docker Compose.

## Architecture

- **Compute Instance**: `e2-medium` VM running Debian 11
- **Services**: PostgreSQL, Airflow Webserver, Airflow Scheduler
- **Storage**: GCS bucket for DAGs, logs, and configurations
- **Networking**: Firewall rule allowing access on port 8081
- **Scheduling**: Cloud Scheduler jobs for automatic start/stop

## Components

### 1. VM Instance (`google_compute_instance.airflow`)
- Runs startup script to install Docker and configure Airflow
- Uses service account for GCP authentication
- Scheduled to run Saturday 8:00 AM to Sunday 00:00 AM (Taiwan Time)

### 2. GCS Bucket (`google_storage_bucket.airflow_bucket`)
- Stores DAG files, logs, and Docker configurations
- Versioning enabled with 30-day lifecycle policy

### 3. Service Accounts
- **Airflow SA**: For Airflow operations (BigQuery, GCS access)
- **Scheduler SA**: For starting/stopping the VM via Cloud Scheduler

### 4. Docker Services
- **PostgreSQL**: Database backend
- **Airflow Webserver**: Web UI on port 8081
- **Airflow Scheduler**: DAG scheduling and execution

## Access Information

- **URL**: `http://<VM_EXTERNAL_IP>:8081`
- **Username**: `admin`
- **Password**: `admin`

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