pipeline {
    agent any
    tools {
        terraform 'Terraform-v1.11.3'
    }
    environment {
        // GCP Project ID - Replace with your actual GCP Project ID
        GCP_PROJECT_ID = 'open-data-v2-cicd'
        // GCS Bucket for Terraform State - Replace with your GCS bucket name
        TF_STATE_BUCKET = 'terraform-state-bucket--data-sharing'
        // GCP Region - Adjust if needed
        GCP_REGION = 'asia-east1'
    }
    stages {
        stage('Checkout Code') {
            steps {
                checkout scm
            }
        }
        stage('Configure GCP Authentication') {
            steps {
                withCredentials([file(credentialsId: 'gcp-sa-key-dev-2', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
                    sh 'gcloud auth activate-service-account --key-file=$GOOGLE_APPLICATION_CREDENTIALS'
                    sh 'gcloud config set project $GCP_PROJECT_ID'
                    sh 'gcloud auth list'
                    sh 'gcloud config list'
                }
            }
        }
        stage('Terraform Init') {
            steps {
                sh 'terraform init -backend-config="bucket=${TF_STATE_BUCKET}"'
            }
        }
        stage('Terraform Validate') {
            steps {
                sh 'terraform validate'
            }
        }
        stage('Terraform Plan') {
            steps {
                sh 'terraform plan -out=tfplan'
                // Optionally, archive the plan file as an artifact for review
                archiveArtifacts artifacts: 'tfplan'
            }
        }
        stage('Terraform Apply') {
            steps {
                // For automated apply (e.g., for dev/staging)
                // sh 'terraform apply tfplan'

                // For main/prod pipeline, consider manual approval step before apply
                input message: 'Approve Terraform Apply to Production?', ok: 'Proceed with Apply'
                // Check if Jenkins is using correct SA
                sh 'gcloud auth list'
                sh 'gcloud config list'
                sh 'terraform apply tfplan'
            }
        }
    }
    post {
        failure {
            script {
                echo "Terraform Pipeline Failed!"
                // Add notifications (e.g., email, Slack) here if needed
            }
        }
        success {
            script {
                echo "Terraform Pipeline Succeeded!"
                // Add notifications here if needed
            }
        }
    }
}
