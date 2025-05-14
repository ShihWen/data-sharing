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
        // Dev environment variables
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
        
        stage('Terraform Init') {
            steps {
                sh 'gcloud auth list'
                sh 'gcloud config list'
                sh 'terraform init -backend-config="bucket=${TF_STATE_BUCKET}" -migrate-state'
            }
        }
        
        stage('Terraform Plan') {
            steps {
                sh 'terraform plan -out=tfplan'
                archiveArtifacts artifacts: 'tfplan'
            }
        }
        stage('Terraform Apply') {
            steps {
                sh 'terraform apply tfplan'
            }
        }
    }
    
    post {
        always {
            echo 'Pipeline finished!'
        }
    }
}
