pipeline {
    agent any
    tools {
        terraform 'Terraform-v1.11.3' // Ensure tool name matches your Jenkins Global Tool Configuration
    }
    parameters { // Added parameters section
        choice(name: 'environment',
               choices: ['dev', 'main'], // Allowed values for the parameter
               description: 'Select the deployment environment')
    }
    environment {
        // --- DEFINE ALL ENVIRONMENT-SPECIFIC VALUES ---
        DEV_GCP_PROJECT_ID = 'open-data-v2-cicd'
        DEV_TF_STATE_BUCKET = 'terraform-state-bucket-project-data-sharing'
        DEV_SA_CREDENTIAL_ID = 'gcp-sa-dev'
        DEV_SERVICE_ACCOUNT_EMAIL = 'jenkins-tf-dev@open-data-v2-cicd.iam.gserviceaccount.com'
         
        PROD_GCP_PROJECT_ID = 'open-data-v2-cicd-prod'
        PROD_TF_STATE_BUCKET = 'terraform-state-bucket-project-data-sharing-prod'
        PROD_SA_CREDENTIAL_ID = 'gcp-sa-prod'
        PROD_SERVICE_ACCOUNT_EMAIL = 'jenkins-tf-prod@open-data-v2-cicd.iam.gserviceaccount.com'

        GOOGLE_APPLICATION_CREDENTIALS = ''

        // --- DYNAMIC ENVIRONMENT VARIABLES (Set in a stage) ---
        // TARGET_GCP_PROJECT_ID
        // TARGET_TF_STATE_BUCKET
        // TARGET_SA_CREDENTIAL_ID
        // TARGET_SERVICE_ACCOUNT_EMAIL

        // GCP_REGION = 'asia-east1' // Your GCP Region (common for both environments)
        // Note: GOOGLE_APPLICATION_CREDENTIALS will be set by withCredentials block
    }
    stages {
        stage('Checkout Code') {
            steps {
                checkout scm
            }
        }
        stage('Determine Environment Variables') { // Added stage to set dynamic variables
            steps {
                script {
                    echo "Selected environment parameter: ${params.environment}"

                    // Set target environment variables based on the 'environment' parameter
                    if (params.environment == 'main') {
                        env.DEPLOYMENT_ENV = 'prod'
                        env.TARGET_GCP_PROJECT_ID = env.PROD_GCP_PROJECT_ID
                        env.TARGET_TF_STATE_BUCKET = env.PROD_TF_STATE_BUCKET
                        env.TARGET_SA_CREDENTIAL_ID = env.PROD_SA_CREDENTIAL_ID
                        env.TARGET_SERVICE_ACCOUNT_EMAIL = env.PROD_SERVICE_ACCOUNT_EMAIL
                        env.GOOGLE_APPLICATION_CREDENTIALS = credentials('gcp-sa-prod')
                        echo "Targeting Production Environment"
                    } else if (params.environment == 'dev') { // Default to dev if parameter is 'dev'
                        env.DEPLOYMENT_ENV = 'dev'
                        env.TARGET_GCP_PROJECT_ID = env.DEV_GCP_PROJECT_ID
                        env.TARGET_TF_STATE_BUCKET = env.DEV_TF_STATE_BUCKET
                        env.TARGET_SA_CREDENTIAL_ID = env.DEV_SA_CREDENTIAL_ID
                        env.TARGET_SERVICE_ACCOUNT_EMAIL = env.DEV_SERVICE_ACCOUNT_EMAIL
                        env.GOOGLE_APPLICATION_CREDENTIALS = credentials('gcp-sa-dev')
                        echo "Targeting Development Environment"
                    } else {
                        // This case should not be reachable with a choice parameter, but good practice
                        error "Invalid environment parameter: ${params.environment}. Please select 'dev' or 'main'."
                    }

                    echo "Target GCP Project ID: ${TARGET_GCP_PROJECT_ID}"
                    echo "Target Terraform State Bucket: ${TARGET_TF_STATE_BUCKET}"
                    echo "Target SA Credential ID: ${TARGET_SA_CREDENTIAL_ID}"
                    echo "Target Service Account Email: ${TARGET_SERVICE_ACCOUNT_EMAIL}"
                }
            }
        }
        stage('Configure GCP Authentication') {
            steps {
                // Use the dynamic credential ID
                withCredentials([file(credentialsId: TARGET_SA_CREDENTIAL_ID, variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
                    sh 'gcloud auth activate-service-account --key-file=$GOOGLE_APPLICATION_CREDENTIALS'
                    sh 'gcloud config set project $TARGET_GCP_PROJECT_ID' // Use TARGET_GCP_PROJECT_ID
                    echo "GCP Authentication Configured for Project: ${TARGET_GCP_PROJECT_ID} as: ${TARGET_SERVICE_ACCOUNT_EMAIL}" // Use TARGET_SERVICE_ACCOUNT_EMAIL
                }
            }
        }
        // Note: Check IAM Policies stage can remain, using TARGET_SERVICE_ACCOUNT_EMAIL and TARGET_GCP_PROJECT_ID
        stage('Check IAM Policies') {
            steps {
                script {
                    echo "Checking IAM Policy for Service Account: ${TARGET_SERVICE_ACCOUNT_EMAIL} in Project: ${TARGET_GCP_PROJECT_ID}"
                    def policyOutput = sh(script: "gcloud iam service-accounts get-iam-policy ${TARGET_SERVICE_ACCOUNT_EMAIL} --project=${TARGET_GCP_PROJECT_ID}", returnStdout: true).trim()
                    echo "IAM Policy:"
                    echo "${policyOutput}"
                }
            }
        }
        stage('Terraform Init') {
            steps {
                // Use dynamic environment variables for Terraform commands
                sh 'terraform init -backend-config="bucket=${TARGET_TF_STATE_BUCKET}" -migrate-state'
            }
        }
        stage('Terraform Validate') {
            steps {
                sh 'terraform validate'
            }
        }
        stage('Terraform Plan') {
            steps {
                // Use dynamic environment variables for Terraform commands
                sh 'terraform plan -out=tfplan'
                archiveArtifacts artifacts: 'tfplan'
            }
        }
        stage('Terraform Apply') {
            steps {
                // Use dynamic environment variable in input message
                input message: "Approve Terraform Apply to ${DEPLOYMENT_ENV} Environment?", ok: 'Proceed with Apply'
                // Use dynamic environment variables for Terraform commands
                sh 'terraform apply tfplan'
            }
        }
    }
    post {
        failure {
            script {
                echo "Terraform Pipeline Failed for ${DEPLOYMENT_ENV} Environment!" // Dynamic failure message
                // TODO: Add failure notifications (e.g., email, Slack)
            }
        }
        success {
            script {
                echo "Terraform Pipeline Succeeded for ${DEPLOYMENT_ENV} Environment!" // Dynamic success message
                // TODO: Add success notifications (e.g., email, Slack)
            }
        }
    }
}
