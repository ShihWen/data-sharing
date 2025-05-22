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
    }
    
    stages {
        stage('Checkout Code') {
            steps {
                checkout scm
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
        
        stage('Terraform Plan') {
            steps {
                dir('terraform') {
                    sh '''
                        terraform plan \
                            -var="project_id=${DEV_GCP_PROJECT_ID}" \
                            -var="aws_access_key=${AWS_CREDENTIALS_USR}" \
                            -var="aws_secret_key=${AWS_CREDENTIALS_PSW}" \
                            -var="s3_bucket=${S3_BUCKET}" \
                            -out=tfplan
                    '''
                    archiveArtifacts artifacts: 'tfplan'
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
