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
        S3_BUCKET = 'online-data-lake-thirty-three'  // You might want to make this configurable per environment
        AIRFLOW_BUCKET = 'open-data-v2-cicd-airflow-storage'  // Add this for Airflow GCS bucket
    }
    
    stages {
        stage('Checkout Code') {
            steps {
                checkout scm
            }
        }
        
        stage('Detect DAG Changes') {
            steps {
                script {
                    // Check if there are any changes in the DAGs directory
                    def dagChanges = sh(
                        script: '''
                            if git diff --name-only HEAD~1 HEAD | grep -q "terraform/airflow/docker/dags/"; then
                                echo "true"
                            else
                                echo "false"
                            fi
                        ''',
                        returnStdout: true
                    ).trim()

                    // Set environment variable for later stages
                    env.DAG_CHANGES = dagChanges
                    
                    if (dagChanges == "true") {
                        echo "DAG changes detected. Will upload to GCS."
                    } else {
                        echo "No DAG changes detected."
                    }
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
                        echo "Running Terraform init..."
                        terraform init -reconfigure -backend-config="bucket=${DEV_TF_STATE_BUCKET}"
                    '''
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
        
        stage('Check and Import Transfer Service Account') {
            steps {
                dir('terraform') {
                    script {
                        // Check if service account exists in GCP
                        sh '''
                            echo "Checking if bigquery-transfer-sa exists in GCP..."
                            if gcloud iam service-accounts describe bigquery-transfer-sa@${DEV_GCP_PROJECT_ID}.iam.gserviceaccount.com --project=${DEV_GCP_PROJECT_ID} > /dev/null 2>&1; then
                                echo "Service account exists in GCP, checking Terraform state..."
                                
                                # Check if service account is in Terraform state at the new location
                                if ! terraform state list | grep -q 'google_service_account.transfer_sa'; then
                                    echo "Service account not in Terraform state at root level, importing..."
                                    terraform import \
                                        -var="project_id=${DEV_GCP_PROJECT_ID}" \
                                        -var="aws_access_key=${AWS_CREDENTIALS_USR}" \
                                        -var="aws_secret_key=${AWS_CREDENTIALS_PSW}" \
                                        -var="s3_bucket=${S3_BUCKET}" \
                                        google_service_account.transfer_sa \
                                        "projects/${DEV_GCP_PROJECT_ID}/serviceAccounts/bigquery-transfer-sa@${DEV_GCP_PROJECT_ID}.iam.gserviceaccount.com"
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
                            echo "Generating full terraform plan..."
                            terraform plan \\
                                -var="project_id=${DEV_GCP_PROJECT_ID}" \\
                                -var="aws_access_key=${AWS_CREDENTIALS_USR}" \\
                                -var="aws_secret_key=${AWS_CREDENTIALS_PSW}" \\
                                -var="s3_bucket=${S3_BUCKET}" \\
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
                        echo "✅ VM was already running and healthy, proceeding with config update..."
                        // VM is already ready, minimal wait
                        sleep(time: 30, unit: 'SECONDS')
                    } else {
                        echo "🔄 VM was created/recreated, waiting for it to be fully ready..."
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
                                            echo "✅ Airflow is healthy and ready!"
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
                            echo "✅ Scheduler configuration updated successfully"
                        else
                            echo "⚠️  Scheduler configuration update failed, but continuing..."
                            echo "This may be due to container naming differences or timing issues"
                            echo "The deployment will continue as this is not critical for basic functionality"
                        fi
                    '''
                }
            }
        }
        */

        stage('Setup Airflow Connections & Variables') {
            steps {
                script {
                    echo "=== Setting up Airflow Connections & Variables ==="
                    
                    // Make the airflow-manager script executable
                    sh '''
                        chmod +x scripts/airflow-manager.sh
                    '''
                    
                    // Check if connections and variables already exist
                    echo "🔍 Checking if Airflow connections and variables already exist..."
                    def connectionsExist = sh(
                        script: '''
                            cd scripts
                            ./airflow-manager.sh check-connections
                        ''',
                        returnStatus: true
                    )

                    if (connectionsExist == 0) {
                        echo "✅ Connections and variables already exist - skipping creation step"
                        echo "This saves time by not recreating existing configurations!"
                    } else {
                        echo "🔗 Connections or variables are missing - creating them now..."
                        sh '''
                            cd scripts
                            ./airflow-manager.sh connections
                        '''
                        echo "✅ Connections and variables have been created successfully"
                    }
                }
            }
        }
    }
    
    post {
        always {
            echo 'Pipeline finished!'
        }
    }
}
