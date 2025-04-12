pipeline {
    agent any
    tools {
        terraform 'Terraform-v1.11.3' // Ensure tool name matches your Jenkins Global Tool Configuration
    }
    environment {
        // --- REPLACE THESE WITH YOUR ACTUAL VALUES ---
        GCP_PROJECT_ID = 'open-data-v2-cicd'
        TF_STATE_BUCKET = 'terraform-state-bucket-project-data-sharing'
        GCP_REGION = 'asia-east1'
        SERVICE_ACCOUNT_EMAIL = 'jenkins-tf-dev@open-data-v2-cicd.iam.gserviceaccount.com'
    }
    stages {
        stage('Checkout Code') {
            steps {
                checkout scm
            }
        }
        stage('Configure GCP Authentication') {
            steps {
                withCredentials([file(credentialsId: 'gcp-sa-dev', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) { // Ensure 'gcp-sa-dev' is your Credential ID in Jenkins
                    sh 'gcloud auth activate-service-account --key-file=$GOOGLE_APPLICATION_CREDENTIALS'
                    sh 'gcloud config set project $GCP_PROJECT_ID'
                    echo "GCP Authentication Configured as: ${SERVICE_ACCOUNT_EMAIL}"

                    sh 'terraform init -backend-config="bucket=${TF_STATE_BUCKET}" -migrate-state'
                    sh 'terraform validate'
                    sh 'terraform plan -out=tfplan'
                    archiveArtifacts artifacts: 'tfplan'
                    input message: 'Approve Terraform Apply to Production?', ok: 'Proceed with Apply'
                    sh 'terraform apply tfplan'
                }
            }
        }
        stage('Check IAM Policies') {
            steps {
                script {
                    echo "Checking IAM Policy for Service Account: ${SERVICE_ACCOUNT_EMAIL}"
                    def policyOutput = sh(script: "gcloud iam service-accounts get-iam-policy ${SERVICE_ACCOUNT_EMAIL}", returnStdout: true).trim()
                    echo "IAM Policy:"
                    echo "${policyOutput}"
                }
            }
        }
        // stage('Terraform Init') {
        //     steps {
        //         sh 'gcloud auth list'
        //         sh 'gcloud config list'
        //         sh 'terraform init -backend-config="bucket=${TF_STATE_BUCKET}" -migrate-state'
        //     }
        // }
        // stage('Terraform Validate') {
        //     steps {
        //         sh 'terraform validate'
        //     }
        // }
        // stage('Terraform Plan') {
        //     steps {
        //         sh 'terraform plan -out=tfplan'
        //         archiveArtifacts artifacts: 'tfplan'
        //     }
        // }
        // stage('Terraform Apply') {
        //     steps {
        //         input message: 'Approve Terraform Apply to Production?', ok: 'Proceed with Apply'
        //         sh 'terraform apply tfplan'
        //     }
        // }
    }
    post {
        failure {
            script {
                echo "Terraform Pipeline Failed!"
                // TODO: Add failure notifications (e.g., email, Slack)
            }
        }
        success {
            script {
                echo "Terraform Pipeline Succeeded!"
                // TODO: Add success notifications (e.g., email, Slack)
            }
        }
    }
}
