pipeline {
    agent any
    
    parameters { // Added parameters section
        choice(name: 'environment',
               choices: ['dev', 'main'], // Allowed values for the parameter
               description: 'Select the deployment environment')
    }
    
    tools {
        terraform 'Terraform-v1.11.3'  // Make sure this matches your Jenkins tool configuration
    }
    
    environment {
        DEV_GCP_PROJECT_ID = 'open-data-v2-cicd'
        DEV_TF_STATE_BUCKET = 'terraform-state-data-sharing-dev-new'
        DEV_SA_CREDENTIAL_ID = 'gcp-sa-dev'  // This will be configured in Jenkins credentials
        GOOGLE_APPLICATION_CREDENTIALS = credentials('gcp-sa-dev')
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
        
        stage('Terraform Plan') {
            steps {
                dir('terraform') {
                    sh 'terraform plan -out=tfplan'
                    archiveArtifacts artifacts: 'tfplan'
                }
            }
        }
        
        stage('Terraform Apply') {
            steps {
                dir('terraform') {
                    sh 'terraform apply tfplan'
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
