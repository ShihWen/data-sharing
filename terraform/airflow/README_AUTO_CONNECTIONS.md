# Airflow Auto-Connections Setup

This document explains how to automatically create Airflow connections and variables every time the VM restarts.

## Problem

When the Airflow VM is restarted (either manually or due to maintenance), the Airflow connections and variables are lost and need to be recreated manually. This requires running `./scripts/airflow-manager.sh connections` after every restart.

## Solution

We've implemented an automatic system that executes the existing `airflow-manager.sh connections` command every time the VM starts up, using systemd services.

## How It Works

### 1. Startup Script Integration

The VM startup script (`terraform/airflow/templates/startup_script.sh.tpl`) now includes:

- **Script Download**: Downloads the latest `airflow-manager.sh` from GCS bucket
- **Systemd Service**: Creates `airflow-connections.service` that automatically runs on boot
- **Service Enablement**: Enables the service to run automatically on every VM restart
- **Fallback**: Creates a minimal fallback script if the main script isn't available

### 2. Systemd Service Details

The `airflow-connections.service` service:

- **Waits for Dependencies**: Ensures Docker is running and Airflow is healthy before executing
- **Health Check**: Polls the Airflow health endpoint until it's available (with timeout)
- **Executes Command**: Runs `/opt/airflow/airflow-manager.sh connections` 
- **Fallback Logic**: Uses minimal connection creation if main script unavailable
- **Runs Once**: Uses `Type=oneshot` to run once per boot and not restart

### 3. Script Management

- **GCS Storage**: The `airflow-manager.sh` script is stored in the GCS bucket at `gs://[bucket]/scripts/airflow-manager.sh`
- **Auto-Download**: VM downloads the latest version on startup
- **Consistency**: Uses the same script as manual operations, ensuring consistency

### 4. Created Connections & Variables

The auto-connections service creates the same connections and variables as `./airflow-manager.sh connections`:

#### Connections:
- `google_cloud_default`: Google Cloud Platform connection with service account authentication

#### Variables:
- `gcp_project_id`, `project_id`, `notification_email`
- `bigquery_location`, `data_retention_days`, `max_parallel_tasks`
- `environment`, `airflow_bucket`
- `tpe_mrt_bronze_dataset_id`, `tpe_mrt_silver_dataset_id`, `tpe_mrt_gold_dataset_id`

## For New VMs

The auto-connections setup is automatically included when you create new VMs via Terraform. The service will:

1. Download the latest `airflow-manager.sh` from GCS
2. Start automatically when the VM boots
3. Wait for Airflow to be healthy
4. Execute `./airflow-manager.sh connections`
5. Log the results

## For Existing VMs

If you have an existing VM and want to add this auto-connections feature, use the setup script:

```bash
# Navigate to the scripts directory
cd scripts

# Make the script executable and run it
chmod +x setup_auto_connections.sh
./setup_auto_connections.sh
```

This script will:
1. Upload `airflow-manager.sh` to GCS bucket
2. Check that the VM is running
3. Download the script to the VM
4. Create and enable the systemd service
5. Test the setup

## Manual Operations

### Check Service Status
```bash
gcloud compute ssh airflow-vm --zone=asia-east1-b --command='sudo systemctl status airflow-connections.service'
```

### View Service Logs
```bash
gcloud compute ssh airflow-vm --zone=asia-east1-b --command='sudo journalctl -u airflow-connections.service'
```

### Run Service Manually
```bash
gcloud compute ssh airflow-vm --zone=asia-east1-b --command='sudo systemctl start airflow-connections.service'
```

### Test airflow-manager Script Directly
```bash
gcloud compute ssh airflow-vm --zone=asia-east1-b --command='sudo /opt/airflow/airflow-manager.sh connections'
```

### Update Script on VM
```bash
# Upload updated script to GCS first
gsutil cp scripts/airflow-manager.sh gs://open-data-v2-cicd-airflow-storage/scripts/airflow-manager.sh

# Then download to VM
gcloud compute ssh airflow-vm --zone=asia-east1-b --command='cd /opt/airflow && sudo gsutil cp gs://open-data-v2-cicd-airflow-storage/scripts/airflow-manager.sh ./airflow-manager.sh && sudo chmod +x ./airflow-manager.sh'
```

### Disable Auto-Connections (if needed)
```bash
gcloud compute ssh airflow-vm --zone=asia-east1-b --command='sudo systemctl disable airflow-connections.service'
```

## Verification

After the VM restarts, verify the connections and variables are created:

1. **Access Airflow UI**: http://[VM_IP]:8081
2. **Check Connections**: Admin → Connections → Look for `google_cloud_default`
3. **Check Variables**: Admin → Variables → Verify all variables are present

## Logs and Troubleshooting

### Service Logs
The service logs all output to systemd journal:
```bash
sudo journalctl -u airflow-connections.service -f
```

### Connection Creation Logs
The startup execution is also logged to:
```bash
tail -f /var/log/airflow-connections.log
```

### Common Issues

1. **Service not running**: Check if Docker and Airflow are healthy first
2. **Timeout errors**: The service waits up to 10 minutes for Airflow to be ready
3. **Script download fails**: Check GCS permissions and bucket access
4. **Connection creation fails**: Verify the service account key is properly mounted
5. **Variables not appearing**: Check Airflow UI and service logs for errors

## Pipeline Integration

The Jenkins pipeline continues to work as before. The `Setup Airflow Connections & Variables` stage will still run during deployments, ensuring connections are available even if the service hasn't run yet.

## Benefits

- **Zero Manual Intervention**: Connections are automatically created on every restart
- **Code Reuse**: Uses the same `airflow-manager.sh` script as manual operations
- **Always Up-to-date**: Downloads latest script version from GCS on each startup
- **Robust and Reliable**: Includes proper error handling and fallback mechanisms  
- **Persistent**: Survives VM restarts, stops, starts, and recreations
- **Logged**: Full logging for troubleshooting and auditing
- **Compatible**: Works alongside existing Jenkins pipeline processes
- **Maintainable**: Single source of truth for connection creation logic 