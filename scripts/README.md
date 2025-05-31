# Airflow Management Scripts

This directory contains a consolidated script for managing the Airflow VM and services.

## Main Script: `airflow-manager.sh`

A comprehensive tool that replaces all the individual scripts with a single, easy-to-use interface.

### Usage

```bash
./airflow-manager.sh [COMMAND]
```

### Available Commands

| Command | Description |
|---------|-------------|
| `validate` | Validate that Airflow is running and accessible |
| `restart` | Restart the Airflow VM safely |
| `fix` | Apply permanent fixes to prevent restart issues |
| `upload` | Upload DAGs to GCS bucket |
| `status` | Show current VM and service status |
| `help` | Show help message |

### Examples

```bash
# Check if Airflow is working
./airflow-manager.sh validate

# Restart the VM
./airflow-manager.sh restart

# Apply permanent fixes to prevent future issues
./airflow-manager.sh fix

# Upload DAGs to GCS
./airflow-manager.sh upload

# Check current status
./airflow-manager.sh status
```

## What This Script Does

### `validate`
- Tests VM connectivity
- Checks if port 8081 is accessible
- Validates Airflow health endpoint
- Verifies web UI accessibility
- Checks Docker service status

### `restart`
- Safely stops the VM
- Starts the VM
- Waits for startup completion
- Validates that Airflow is working after restart

### `fix`
- Creates necessary users (airflow, airflow-container)
- Sets up proper directory permissions
- Configures systemd services for automatic startup
- Updates GCS sync service with proper authentication
- Ensures all fixes persist through reboots

### `upload`
- Syncs local DAG files to GCS bucket
- Uses `gsutil rsync` for efficient uploads

### `status`
- Shows VM status and IP
- Lists Docker container status
- Shows systemd service status

## Backup

All original scripts have been moved to the `backup/` directory for reference.

## Configuration

The script uses these default values:
- Project ID: `open-data-v2-cicd`
- Zone: `asia-east1-b`
- VM Name: `airflow-vm`
- GCS Bucket: `open-data-v2-cicd-airflow-storage`

These can be modified at the top of the script if needed.

## Permanent Fixes Applied

When you run `./airflow-manager.sh fix`, the following permanent fixes are applied:

1. **User Management**: Creates `airflow` and `airflow-container` users with proper UIDs
2. **Permission Services**: Sets up systemd services that fix permissions on every boot
3. **GCS Sync**: Configures GCS sync service with proper authentication
4. **Directory Structure**: Creates all necessary directories with correct ownership
5. **Docker Integration**: Ensures Docker services start properly

These fixes ensure that VM restarts will work smoothly without manual intervention. 