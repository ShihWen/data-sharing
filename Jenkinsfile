pipeline {
    agent any
    
    tools {
        terraform 'Terraform-v1.11.3'  // Make sure this matches your Jenkins tool configuration
    }
    
    environment {
        // Dev environment variables
        DEV_GCP_PROJECT_ID = 'open-data-v2-cicd'
        DEV_TF_STATE_BUCKET = 'terraform-state-data-sharing-dev-new'
        DEV_SA_CREDENTIAL_ID = 'gcp-sa-dev'  // This will be configured in Jenkins credentials
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Terraform Init') {
            steps {
                dir('terraform') {
                    withCredentials([file(credentialsId: env.DEV_SA_CREDENTIAL_ID, variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
                        sh """
                            echo "Authenticating with GCP..."
                            gcloud auth activate-service-account --key-file=\$GOOGLE_APPLICATION_CREDENTIALS
                            gcloud config set project ${env.DEV_GCP_PROJECT_ID}
                            
                            echo "Running Terraform init..."
                            terraform init -backend-config="bucket=${env.DEV_TF_STATE_BUCKET}" -migrate-state
                        """
                    }
                }
            }
        }
        
        stage('Terraform Plan') {
            steps {
                dir('terraform') {
                    withCredentials([file(credentialsId: env.DEV_SA_CREDENTIAL_ID, variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
                        sh 'terraform plan'
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
