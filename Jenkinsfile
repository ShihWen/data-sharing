pipeline {
    agent any
    
    tools {
        terraform 'Terraform-v1.11.3'  // Make sure this matches your Jenkins tool configuration
    }
    
    environment {
        DEV_GCP_PROJECT_ID = 'open-data-v2-cicd'
        DEV_TF_STATE_BUCKET = 'terraform-state-data-sharing-dev-new'
        DEV_SA_CREDENTIAL_ID = 'gcp-sa-dev'  // This will be configured in Jenkins credentials
        GOOGLE_APPLICATION_CREDENTIALS = credentials('gcp-sa-dev')
        AWS_CREDENTIALS = credentials('aws-s3-credentials')  // Add this credential in Jenkins
        TDX_API_CREDENTIALS = credentials('tdx-api-credentials')
        S3_BUCKET = 'online-data-lake-thirty-three'  // You might want to make this configurable per environment
        AIRFLOW_BUCKET = 'open-data-v2-cicd-airflow-storage'  // Add this for Airflow GCS bucket
        GCS_DATA_LAKE_BUCKET = 'open-data-v2-cicd-data-lake'
    }
    
    stages {
        stage('Checkout Code') {
            steps {
                checkout scm
                // Unshallow the clone to ensure we can diff against previous commits.
                // Some git servers don't support --unshallow, so we fall back to fetching more history.
                sh 'git fetch --unshallow || git fetch --depth=100'
            }
        }
        
        stage('Detect DAG Changes') {
            steps {
                script {
                    def changedFilesScript
                    if (env.GIT_PREVIOUS_SUCCESSFUL_COMMIT) {
                        echo "Comparing changes between previous successful commit (${env.GIT_PREVIOUS_SUCCESSFUL_COMMIT}) and current commit (${env.GIT_COMMIT})"
                        changedFilesScript = "git diff --name-only ${env.GIT_PREVIOUS_SUCCESSFUL_COMMIT} ${env.GIT_COMMIT}"
                    } else {
                        echo "No previous successful commit found. Checking for changes in the current commit (${env.GIT_COMMIT})."
                        // This is more reliable for different commit types (e.g., merge commits)
                        changedFilesScript = 'git diff-tree --no-commit-id --name-only -r HEAD'
                    }

                    def changedFiles = sh(script: changedFilesScript, returnStdout: true).trim()
                    echo "Files changed:\n${changedFiles}"

                    def dagChanges = sh(
                        script: """
                            echo '${changedFiles}' | grep -q "terraform/airflow/docker/dags/" && echo "true" || echo "false"
                        """,
                        returnStdout: true
                    ).trim()

                    // Detect changes in Terraform files (excluding DAGs)
                    def tfChanges = sh(
                        script: """
                            echo '${changedFiles}' | grep -E "^terraform/" | grep -qv "terraform/airflow/docker/dags/" && echo "true" || echo "false"
                        """,
                        returnStdout: true
                    ).trim()

                    env.DAG_CHANGES = dagChanges
                    env.TF_CHANGES = tfChanges
                    
                    if (dagChanges == "true") {
                        echo "DAG changes detected."
                    }
                    if (tfChanges == "true") {
                        echo "Terraform infrastructure changes detected."
                    }
                }
            }
        }

        stage('Upload Airflow Configuration') {
            when {
                anyOf {
                    changeset "terraform/airflow/docker/Dockerfile"
                    changeset "terraform/airflow/docker/requirements.txt"
                    changeset "terraform/airflow/docker/docker-compose.yml"
                    changeset "terraform/airflow/docker/config/**"
                }
            }
            steps {
                script {
                    sh '''
                        echo "Uploading core Airflow configuration files to GCS..."
                        # Use rsync to sync the entire docker config directory, which is more robust
                        # and includes Dockerfile, requirements.txt, and docker-compose.yml
                        gsutil rsync -r -d terraform/airflow/docker/ gs://${AIRFLOW_BUCKET}/docker/
                        echo "SUCCESS: Core configuration directory synced."
                    '''
                }
            }
        }

        stage('Upload Airflow Manager Script') {
            when {
                changeset "scripts/airflow-manager.sh"
            }
            steps {
                script {
                    sh '''
                        echo "Uploading airflow-manager.sh script to GCS..."
                        gsutil cp scripts/airflow-manager.sh gs://${AIRFLOW_BUCKET}/scripts/airflow-manager.sh
                        echo "SUCCESS: Airflow manager script uploaded to GCS"
                        echo "This ensures the startup script can download and use the full script instead of the fallback"
                    '''
                }
            }
        }

        stage('Upload DAGs to GCS') {
            when {
                expression { return env.DAG_CHANGES == "true" }
            }
            steps {
                script {
                    // Authenticate with GCP
                    sh '''
                        echo "Authenticating with GCP..."
                        gcloud auth activate-service-account --key-file=$GOOGLE_APPLICATION_CREDENTIALS
                        gcloud config set project ${DEV_GCP_PROJECT_ID}
                    '''

                    // Use the upload_config script to sync DAGs
                    sh '''
                        echo "Running upload_config.sh to sync DAGs..."
                        cd scripts
                        chmod +x upload_config.sh
                        ./upload_config.sh
                    '''
                }
            }
        }

        stage('Setup Environment') {
            steps {
                script {
                    // Change to terraform directory
                    dir('terraform') {
                        // Authenticate with GCP
                        sh '''
                            echo "Authenticating with GCP..."
                            gcloud auth activate-service-account --key-file=$GOOGLE_APPLICATION_CREDENTIALS
                            gcloud config set project ${DEV_GCP_PROJECT_ID}
                        '''
                        
                        // Create GCS bucket if it doesn't exist
                        sh '''
                            echo "Checking if GCS bucket exists..."
                            if ! gsutil ls -b gs://${DEV_TF_STATE_BUCKET} > /dev/null 2>&1; then
                                echo "Creating GCS bucket for Terraform state..."
                                gsutil mb -p ${DEV_GCP_PROJECT_ID} -l us-central1 gs://${DEV_TF_STATE_BUCKET}
                                gsutil versioning set on gs://${DEV_TF_STATE_BUCKET}
                            else
                                echo "GCS bucket already exists"
                            fi
                        '''
                        
                        // List current auth and config for debugging
                        sh '''
                            echo "Current GCP Authentication:"
                            gcloud auth list
                            echo "Current GCP Configuration:"
                            gcloud config list
                        '''
                    }
                }
            }
        }
        
        stage('Terraform Init') {
            steps {
                dir('terraform') {
                    // Run terraform init with reconfigure flag
                    sh '''
                        echo "Cleaning up previous Terraform state..."
                        rm -rf .terraform .terraform.lock.hcl
                        echo "Running Terraform init..."
                        terraform init -reconfigure -upgrade -backend-config="bucket=${DEV_TF_STATE_BUCKET}"
                        echo "Verifying provider versions after init..."
                        terraform providers
                    '''
                }
            }
        }

        stage('Import Existing Resources') {
            steps {
                dir('terraform') {
                    script {
                        sh '''
                            # This stage imports resources that may already exist in GCP to prevent
                            # errors when Terraform tries to create them again.

                            echo "INFO: Checking for resources that may need to be imported into Terraform state."

                            # Import the BigQuery Data Transfer API service if it's not in state
                            if ! terraform state list | grep -q 'google_project_service.enable_transfer'; then
                                echo "INFO: BigQuery Data Transfer API service not found in state. Checking GCP..."
                                if gcloud services list --enabled --filter="config.name=bigquerydatatransfer.googleapis.com" --format="value(config.name)" | grep -q "."; then
                                    echo "INFO: API is enabled in GCP. Importing into Terraform state..."
                                    terraform import \
                                        google_project_service.enable_transfer \
                                        "${DEV_GCP_PROJECT_ID}/bigquerydatatransfer.googleapis.com"
                                else
                                    echo "INFO: API not enabled in GCP. Terraform will enable it."
                                fi
                            else
                                echo "INFO: BigQuery Data Transfer API service already in state."
                            fi
                            
                            # Import the bigquery-transfer-sa service account if it's not in state
                            if ! terraform state list | grep -q 'google_service_account.transfer_sa'; then
                                echo "INFO: bigquery-transfer-sa not found in state. Checking GCP..."
                                if gcloud iam service-accounts describe bigquery-transfer-sa@${DEV_GCP_PROJECT_ID}.iam.gserviceaccount.com --project=${DEV_GCP_PROJECT_ID} > /dev/null 2>&1; then
                                    echo "INFO: Service account exists in GCP. Importing into Terraform state..."
                                    terraform import \
                                        google_service_account.transfer_sa \
                                        "projects/${DEV_GCP_PROJECT_ID}/serviceAccounts/bigquery-transfer-sa@${DEV_GCP_PROJECT_ID}.iam.gserviceaccount.com"
                                else
                                    echo "INFO: Service account does not exist in GCP. Terraform will create it."
                                fi
                            else
                                echo "INFO: bigquery-transfer-sa already in Terraform state."
                            fi
                        '''
                    }
                }
            }
        }

        stage('Check and Import Service Account') {
            steps {
                dir('terraform') {
                    script {
                        // Check if service account exists in GCP
                        sh '''
                            echo "Checking if service account exists in GCP..."
                            if gcloud iam service-accounts describe airflow-scheduler-sa@${DEV_GCP_PROJECT_ID}.iam.gserviceaccount.com --project=${DEV_GCP_PROJECT_ID} > /dev/null 2>&1; then
                                echo "Service account exists in GCP, checking Terraform state..."
                                
                                # Check if service account is in Terraform state
                                if ! terraform state list | grep -q 'module.airflow.google_service_account.scheduler_sa'; then
                                    echo "Service account not in Terraform state, importing..."
                                    terraform import \
                                        -var="project_id=${DEV_GCP_PROJECT_ID}" \
                                        -var="aws_access_key=${AWS_CREDENTIALS_USR}" \
                                        -var="aws_secret_key=${AWS_CREDENTIALS_PSW}" \
                                        -var="s3_bucket=${S3_BUCKET}" \
                                        -var="gcs_data_lake_bucket=${GCS_DATA_LAKE_BUCKET}" \
                                        -var="tdx_client_id=${TDX_API_CREDENTIALS_USR}" \
                                        -var="tdx_client_secret=${TDX_API_CREDENTIALS_PSW}" \
                                        module.airflow.google_service_account.scheduler_sa \
                                        "projects/${DEV_GCP_PROJECT_ID}/serviceAccounts/airflow-scheduler-sa@${DEV_GCP_PROJECT_ID}.iam.gserviceaccount.com"
                                else
                                    echo "Service account already in Terraform state"
                                fi
                            else
                                echo "Service account does not exist in GCP, will be created by Terraform"
                            fi
                        '''
                    }
                }
            }
        }
        
        stage('Terraform Plan') {
            steps {
                dir('terraform') {
                    script {
                        // Create a full plan. Terraform is idempotent and will not recreate
                        // resources that are already up-to-date.
                        sh '''
                            set -eu
                            echo "Verifying provider versions before plan..."
                            terraform providers
                            echo "Generating full terraform plan..."
                            terraform plan \\
                                -var="project_id=${DEV_GCP_PROJECT_ID}" \\
                                -var="aws_access_key=${AWS_CREDENTIALS_USR}" \\
                                -var="aws_secret_key=${AWS_CREDENTIALS_PSW}" \\
                                -var="s3_bucket=${S3_BUCKET}" \\
                                -var="gcs_data_lake_bucket=${GCS_DATA_LAKE_BUCKET}" \\
                                -var="tdx_client_id=${TDX_API_CREDENTIALS_USR}" \\
                                -var="tdx_client_secret=${TDX_API_CREDENTIALS_PSW}" \\
                                -out=tfplan
                        '''
                        archiveArtifacts artifacts: 'tfplan'
                    }
                }
            }
        }
        
        stage('Terraform Apply') {
            steps {
                dir('terraform') {
                    sh '''
                        terraform apply tfplan
                    '''
                }
            }
        }

        /*
        stage('Update Scheduler Configuration') {
            steps {
                script {
                    echo "=== Updating Scheduler Configuration ==="
                    
                    // Check if VM was recreated or already existed
                    if (env.SKIP_VM_RECREATION == 'true') {
                        echo "SUCCESS: VM was already running and healthy, proceeding with config update..."
                        // VM is already ready, minimal wait
                        sleep(time: 30, unit: 'SECONDS')
                    } else {
                        echo "VM was created/recreated, waiting for it to be fully ready..."
                        // VM was just created, need to wait longer
                        sleep(time: 180, unit: 'SECONDS') // Wait 3 minutes for startup
                        
                        // Wait for Airflow to be healthy
                        timeout(time: 10, unit: 'MINUTES') {
                            waitUntil {
                                script {
                                    def vmIp = sh(
                                        script: '''
                                            gcloud compute instances describe airflow-vm \
                                                --project=${DEV_GCP_PROJECT_ID} \
                                                --zone=asia-east1-b \
                                                --format='get(networkInterfaces[0].accessConfigs[0].natIP)' 2>/dev/null || echo ''
                                        ''',
                                        returnStdout: true
                                    ).trim()
                                    
                                    if (vmIp) {
                                        def healthCheck = sh(
                                            script: "curl -s -o /dev/null -w '%{http_code}' http://${vmIp}:8081/health || echo '000'",
                                            returnStdout: true
                                        ).trim()
                                        
                                        if (healthCheck == '200') {
                                            echo "SUCCESS: Airflow is healthy and ready!"
                                            return true
                                        } else {
                                            echo "⏳ Waiting for Airflow to be healthy... (HTTP ${healthCheck})"
                                            return false
                                        }
                                    } else {
                                        echo "⏳ Waiting for VM IP..."
                                        return false
                                    }
                                }
                            }
                        }
                    }
                    
                    // Make the script executable
                    sh '''
                        chmod +x scripts/update_airflow_config.sh
                    '''
                    
                    // Update scheduler configuration (with error handling)
                    sh '''
                        echo "📝 Running scheduler configuration update..."
                        if ./scripts/update_airflow_config.sh scheduler terraform/airflow/docker/config/airflow.cfg; then
                            echo "SUCCESS: Scheduler configuration updated successfully"
                        else
                            echo "WARNING: Scheduler configuration update failed, but continuing..."
                            echo "This may be due to container naming differences or timing issues"
                            echo "The deployment will continue as this is not critical for basic functionality"
                        fi
                    '''
                }
            }
        }
        */

        /*
        stage('Setup Airflow Connections & Variables') {
            steps {
                script {
                    echo "=== Setting up Airflow Connections & Variables ==="
                    
                    // NOTE: This stage has been commented out because:
                    // 1. The startup script now handles connections and variables automatically
                    // 2. SSH access from Jenkins to the VM was unreliable and caused failures
                    // 3. The startup script runs directly on the VM and is more reliable
                    // 4. All DAGs are now automatically unpaused after connections are created
                    
                    echo "SKIPPED: Connections and variables are now handled automatically by the startup script"
                    echo "The startup script creates all necessary connections, variables, and unpauses all DAGs"
                    echo "This eliminates the need for external SSH connections and ensures reliability"
                }
            }
        }
        */
    }
    
    post {
        always {
            echo 'Pipeline finished!'
        }
    }
}
