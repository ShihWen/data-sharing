pipeline {
    agent any
    tools {
        terraform 'Terraform-v1.11.3'
    }
    parameters {
        choice(name: 'ENVIRONMENT', choices: ['dev', 'prod'], description: 'Select environment to deploy')
    }
    environment {
        GCP_PROJECT_ID = ''
        TF_STATE_BUCKET = ''
        SERVICE_ACCOUNT_EMAIL = ''
        GOOGLE_APPLICATION_CREDENTIALS = ''
        GCP_REGION = 'asia-east1'
    }
    stages {
        stage('Set Environment Config') {
            steps {
                script {
                    if (params.ENVIRONMENT == 'dev') {
                        env.GCP_PROJECT_ID = 'open-data-v2-cicd'
                        env.TF_STATE_BUCKET = 'terraform-state-bucket-project-data-sharing'
                        env.SERVICE_ACCOUNT_EMAIL = 'jenkins-tf-dev@open-data-v2-cicd.iam.gserviceaccount.com'
                        env.GOOGLE_APPLICATION_CREDENTIALS = credentials('gcp-sa-dev')
                    } else if (params.ENVIRONMENT == 'prod') {
                        env.GCP_PROJECT_ID = 'open-data-v2-cicd-prod'
                        env.TF_STATE_BUCKET = 'terraform-state-bucket-project-data-sharing-prod'
                        env.SERVICE_ACCOUNT_EMAIL = 'jenkins-tf-prod@open-data-v2-cicd-prod.iam.gserviceaccount.com'
                        env.GOOGLE_APPLICATION_CREDENTIALS = credentials('gcp-sa-prod')
                    }
                }
            }
        }

        stage('Checkout Code') {
            steps {
                checkout scm
            }
        }

        stage('Configure GCP Authentication') {
            steps {
                withCredentials([file(credentialsId: env.GOOGLE_APPLICATION_CREDENTIALS, variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
                    sh 'gcloud auth activate-service-account --key-file=$GOOGLE_APPLICATION_CREDENTIALS'
                    sh 'gcloud config set project $GCP_PROJECT_ID'
                    echo "GCP Authentication Configured as: ${SERVICE_ACCOUNT_EMAIL}"
                }
            }
        }

        stage('Check IAM Policies') {
            steps {
                script {
                    echo "Checking IAM Policy for Service Account: ${SERVICE_ACCOUNT_EMAIL}"
                    def policyOutput = sh(script: "gcloud iam service-accounts get-iam-policy ${SERVICE_ACCOUNT_EMAIL}", returnStdout: true).trim()
                    echo "IAM Policy:\n${policyOutput}"
                }
            }
        }

        stage('Terraform Init') {
            steps {
                sh 'gcloud auth list'
                sh 'gcloud config list'
                sh "terraform init -backend-config=\"bucket=${TF_STATE_BUCKET}\" -migrate-state"
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
                archiveArtifacts artifacts: 'tfplan'
            }
        }

        stage('Terraform Apply') {
            steps {
                script {
                    if (params.ENVIRONMENT == 'prod') {
                        input message: 'Approve Terraform Apply to Production?', ok: 'Proceed with Apply'
                    }
                }
                sh 'terraform apply tfplan'
            }
        }
    }

    post {
        failure {
            script {
                echo "Terraform Pipeline Failed!"
                // Optional: Add notification logic here
            }
        }
        success {
            script {
                echo "Terraform Pipeline Succeeded!"
                // Optional: Add notification logic here
            }
        }
    }
}
