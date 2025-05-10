
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
        PROD_SERVICE_ACCOUNT_EMAIL = 'jenkins-tf-prod@open-data-v2-cicd-prod.iam.gserviceaccount.com'
        
        //GOOGLE_APPLICATION_CREDENTIALS = credentials("${MYENV_VAR}")
        
        // --- Dynamic Environment Variables (Set in a stage) ---
        // These will be set in the 'Determine Environment Variables' stage
        // TARGET_GCP_PROJECT_ID
        // TARGET_TF_STATE_BUCKET
        // TARGET_SA_CREDENTIAL_ID
        // TARGET_SERVICE_ACCOUNT_EMAIL
        // DEPLOYMENT_ENV

        // GCP_REGION = 'asia-east1' // Your GCP Region (common for both environments)
        // Note: GOOGLE_APPLICATION_CREDENTIALS variable is managed by withCredentials
    }
    stages {
        stage('Checkout Code') {
            steps {
                checkout scm
            }
        }
        stage('Determine Environment Variables') {
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
                        echo "Targeting Production Environment"
                    } else if (params.environment == 'dev') {
                        env.DEPLOYMENT_ENV = 'dev'
                        env.TARGET_GCP_PROJECT_ID = env.DEV_GCP_PROJECT_ID
                        env.TARGET_TF_STATE_BUCKET = env.DEV_TF_STATE_BUCKET
                        env.TARGET_SA_CREDENTIAL_ID = env.DEV_SA_CREDENTIAL_ID
                        env.TARGET_SERVICE_ACCOUNT_EMAIL = env.DEV_SERVICE_ACCOUNT_EMAIL
                        echo "Targeting Development Environment"
                    } else {
                        error "Invalid environment parameter: ${params.environment}. Please select 'dev' or 'main'."
                    }

                    echo "Target GCP Project ID: ${TARGET_GCP_PROJECT_ID}"
                    echo "Target Terraform State Bucket: ${TARGET_TF_STATE_BUCKET}"
                    echo "Target SA Credential ID: ${TARGET_SA_CREDENTIAL_ID}"
                    echo "Target Service Account Email: ${TARGET_SERVICE_ACCOUNT_EMAIL}"
                }
            }
        }
        stage('Terraform Init') {
            steps {
                script {
                    withCredentials([file(credentialsId: env.TARGET_SA_CREDENTIAL_ID, variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
                        dir('terraform') {
                            sh """
                                echo "Authenticating with service account: ${env.TARGET_SERVICE_ACCOUNT_EMAIL}"
                                gcloud auth activate-service-account --key-file=$GOOGLE_APPLICATION_CREDENTIALS
                                gcloud config set project ${env.TARGET_GCP_PROJECT_ID}
                                gcloud storage ls gs://${env.TARGET_TF_STATE_BUCKET}
                            """
                            sh 'terraform init -backend-config="bucket=${TARGET_TF_STATE_BUCKET}" -migrate-state'
                        }
                    }
                }
            }
        }

        stage('Terraform Validate') {
            steps {
                dir('terraform'){
                    sh 'terraform validate'
                }             
            }
        }
        stage('Terraform Plan') {
            steps {
                script {
                    withCredentials([file(credentialsId: env.TARGET_SA_CREDENTIAL_ID, variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
                        dir('terraform') {
                            sh """
                                echo "Authenticating with service account: ${env.TARGET_SERVICE_ACCOUNT_EMAIL}"
                                gcloud auth activate-service-account --key-file=$GOOGLE_APPLICATION_CREDENTIALS
                                gcloud config set project ${env.TARGET_GCP_PROJECT_ID}
                                terraform plan -out=tfplan -var-file=environments/${env.DEPLOYMENT_ENV}.tfvars
                            """
                            archiveArtifacts artifacts: 'tfplan'
                        }
                    }
                }
            }
        }
        stage('Terraform Apply') {
            steps {
                script {
                    if (params.environment == 'main') {
                        echo "Manual approval required for ${env.DEPLOYMENT_ENV} environment."
                        input message: "Approve Terraform Apply to ${env.DEPLOYMENT_ENV} Environment?", ok: 'Proceed with Apply'
                    } else {
                        echo "Auto-applying to ${env.DEPLOYMENT_ENV} environment."
                    }
        
                    withCredentials([file(credentialsId: env.TARGET_SA_CREDENTIAL_ID, variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
                        dir('terraform') {
                            sh """
                                echo "Authenticating with service account: ${env.TARGET_SERVICE_ACCOUNT_EMAIL}"
                                gcloud auth activate-service-account --key-file=$GOOGLE_APPLICATION_CREDENTIALS
                                gcloud config set project ${env.TARGET_GCP_PROJECT_ID}
                                terraform apply tfplan
                            """
                        }
                    }
                }
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
