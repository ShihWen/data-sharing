pipeline {
    agent any
    tools {
        terraform 'Terraform-v1.11.3'
    }
    parameters {
        choice(name: 'environment',
               choices: ['dev', 'main'],
               description: 'Select the deployment environment')
    }
    environment {
        DEV_GCP_PROJECT_ID = 'open-data-v2-cicd'
        DEV_TF_STATE_BUCKET = 'terraform-state-bucket-project-data-sharing'
        DEV_SA_CREDENTIAL_ID = 'gcp-sa-dev'
        DEV_SERVICE_ACCOUNT_EMAIL = 'jenkins-tf-dev@open-data-v2-cicd.iam.gserviceaccount.com'

        PROD_GCP_PROJECT_ID = 'open-data-v2-cicd-prod'
        PROD_TF_STATE_BUCKET = 'terraform-state-bucket-project-data-sharing-prod'
        PROD_SA_CREDENTIAL_ID = 'gcp-sa-prod'
        PROD_SERVICE_ACCOUNT_EMAIL = 'jenkins-tf-prod@open-data-v2-cicd-prod.iam.gserviceaccount.com'
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
                    withCredentials([file(credentialsId: env.TARGET_SA_CREDENTIAL_ID, variable: 'SA_KEY_FILE')]) {
                        dir('terraform') {
                            writeFile file: 'tmp_sa_key.json', text: readFile(SA_KEY_FILE)
                            sh """
                                # Write and secure the credentials file
                                chmod 600 tmp_sa_key.json
                                
                                gcloud auth activate-service-account --key-file=tmp_sa_key.json
                                gcloud config set project ${env.TARGET_GCP_PROJECT_ID}
                                
                                # Get access token for Terraform
                                ACCESS_TOKEN=\$(gcloud auth print-access-token)
                                
                                # Debug: Test bucket access
                                echo "Testing bucket access..."
                                gcloud storage ls gs://${TARGET_TF_STATE_BUCKET}/ || true
                                
                                # Initialize Terraform with debug output
                                echo "Running Terraform init..."
                                GOOGLE_OAUTH_ACCESS_TOKEN=\$ACCESS_TOKEN TF_LOG=DEBUG terraform init \\
                                  -backend-config="bucket=${TARGET_TF_STATE_BUCKET}" \\
                                  -backend-config="access_token=\$ACCESS_TOKEN" \\
                                  -migrate-state
                                
                                # Clean up
                                rm -f tmp_sa_key.json
                            """
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
                    withCredentials([file(credentialsId: env.TARGET_SA_CREDENTIAL_ID, variable: 'SA_KEY_FILE')]) {
                        dir('terraform') {
                            writeFile file: 'tmp_sa_key.json', text: readFile(SA_KEY_FILE)
                            sh """
                                export GOOGLE_APPLICATION_CREDENTIALS=\$PWD/tmp_sa_key.json
                                terraform plan -out=tfplan -var-file=environments/${env.DEPLOYMENT_ENV}.tfvars
                            """
                            sh 'rm -f tmp_sa_key.json'
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
                    }

                    withCredentials([file(credentialsId: env.TARGET_SA_CREDENTIAL_ID, variable: 'SA_KEY_FILE')]) {
                        dir('terraform') {
                            writeFile file: 'tmp_sa_key.json', text: readFile(SA_KEY_FILE)
                            sh """
                                export GOOGLE_APPLICATION_CREDENTIALS=\$PWD/tmp_sa_key.json
                                gcloud auth activate-service-account --key-file=\$GOOGLE_APPLICATION_CREDENTIALS
                                gcloud config set project ${env.TARGET_GCP_PROJECT_ID}
                                terraform apply tfplan
                            """
                            sh 'rm -f tmp_sa_key.json'
                        }
                    }
                }
            }
        }
    }
    post {
        failure {
            script {
                echo "Pipeline failed for ${DEPLOYMENT_ENV} environment"
            }
        }
        success {
            script {
                echo "Pipeline succeeded for ${DEPLOYMENT_ENV} environment"
            }
        }
    }
}
