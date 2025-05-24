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

                    // Upload only the DAGs directory to GCS
                    sh '''
                        echo "Uploading DAGs to GCS..."
                        gsutil -m cp -r terraform/airflow/docker/dags/* gs://${AIRFLOW_BUCKET}/docker/dags/
                        echo "DAGs uploaded successfully to gs://${AIRFLOW_BUCKET}/docker/dags/"
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
        
        stage('Check Airflow VM Status') {
            steps {
                script {
                    // First, find the VM's zone
                    def vmZone = sh(
                        script: '''
                            gcloud compute instances list \
                                --project=${DEV_GCP_PROJECT_ID} \
                                --filter="name=airflow-vm" \
                                --format='get(zone)' 2>/dev/null || echo 'NOT_FOUND'
                        ''',
                        returnStdout: true
                    ).trim()

                    if (vmZone == 'NOT_FOUND') {
                        echo "Airflow VM not found. Will create new VM."
                        env.SKIP_VM_RECREATION = 'false'
                    } else {
                        // Extract zone name from full path
                        vmZone = vmZone.split('/')[-1]
                        echo "Found Airflow VM in zone: ${vmZone}"
                        
                        // Check VM status in the correct zone
                        def vmStatus = sh(
                            script: """
                                gcloud compute instances describe airflow-vm \
                                    --project=${DEV_GCP_PROJECT_ID} \
                                    --zone=${vmZone} \
                                    --format='get(status)' 2>/dev/null || echo 'NOT_FOUND'
                            """,
                            returnStdout: true
                        ).trim()

                        // Check if Airflow is healthy if VM is running
                        if (vmStatus == 'RUNNING') {
                            def vmIp = sh(
                                script: """
                                    gcloud compute instances describe airflow-vm \
                                        --project=${DEV_GCP_PROJECT_ID} \
                                        --zone=${vmZone} \
                                        --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
                                """,
                                returnStdout: true
                            ).trim()
                            
                            def airflowHealth = sh(
                                script: "curl -s -o /dev/null -w '%{http_code}' http://${vmIp}:8081/health || echo '000'",
                                returnStdout: true
                            ).trim()

                            if (airflowHealth == '200') {
                                echo "Airflow VM is running and healthy. Will skip VM recreation but apply other changes."
                                env.SKIP_VM_RECREATION = 'true'
                            } else {
                                echo "Airflow VM is running but not healthy. Will recreate VM."
                                env.SKIP_VM_RECREATION = 'false'
                            }
                        } else {
                            echo "Airflow VM exists but is not running (status: ${vmStatus}). Will recreate VM."
                            env.SKIP_VM_RECREATION = 'false'
                        }
                    }
                }
            }
        }
        
        stage('Terraform Plan') {
            steps {
                dir('terraform') {
                    script {
                        if (env.SKIP_VM_RECREATION == 'true') {
                            // Create a targeted plan that excludes the VM
                            sh '''
                                # Get all resources except the VM
                                RESOURCES=$(terraform state list | grep -v "module.airflow.google_compute_instance.airflow")
                                
                                # Create plan targeting all resources except the VM
                                TARGET_ARGS=""
                                while IFS= read -r resource; do
                                    TARGET_ARGS="$TARGET_ARGS -target='$resource'"
                                done <<< "$RESOURCES"
                                
                                terraform plan \
                                    -var="project_id=${DEV_GCP_PROJECT_ID}" \
                                    -var="aws_access_key=${AWS_CREDENTIALS_USR}" \
                                    -var="aws_secret_key=${AWS_CREDENTIALS_PSW}" \
                                    -var="s3_bucket=${S3_BUCKET}" \
                                    $TARGET_ARGS \
                                    -out=tfplan
                            '''
                        } else {
                            // Create a full plan including VM
                            sh '''
                                terraform plan \
                                    -var="project_id=${DEV_GCP_PROJECT_ID}" \
                                    -var="aws_access_key=${AWS_CREDENTIALS_USR}" \
                                    -var="aws_secret_key=${AWS_CREDENTIALS_PSW}" \
                                    -var="s3_bucket=${S3_BUCKET}" \
                                    -out=tfplan
                            '''
                        }
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
    }
    
    post {
        always {
            echo 'Pipeline finished!'
        }
    }
}
