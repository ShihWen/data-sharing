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

        // --- Define a single stage to handle GCP & Terraform Operations ---
        stage('Run GCP & Terraform Operations') {
            steps {
                // All steps for this stage requiring credentials or specific directories go here

                // Start the withCredentials block (wraps subsequent steps)
                withCredentials([file(credentialsId: TARGET_SA_CREDENTIAL_ID, variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {

                    // Perform initial gcloud authentication and project configuration once
                    sh 'gcloud auth activate-service-account --key-file=$GOOGLE_APPLICATION_CREDENTIALS'
                    sh 'gcloud config set project $TARGET_GCP_PROJECT_ID'
                    echo "GCP Authentication Configured for Project: ${TARGET_GCP_PROJECT_ID} as: ${TARGET_SERVICE_ACCOUNT_EMAIL}"

                    // Optional: gsutil test can be here
                    // echo "Testing GCS Bucket Access with gsutil..."
                    // sh "gsutil ls gs://${TARGET_TF_STATE_BUCKET}"
                    // echo "GCS Bucket Access Test Completed."

                    // Navigate into the terraform directory (wraps subsequent steps)
                    dir('terraform') { // Assume your Terraform code is in a 'terraform' subfolder

                        // --- Terraform Operations ---

                        // Check IAM Policies (runs inside 'terraform' dir, after gcloud auth)
                        script {
                           echo "Checking IAM Policy for Service Account: ${TARGET_SERVICE_ACCOUNT_EMAIL} in Project: ${TARGET_GCP_PROJECT_ID}"
                           // Ensure gcloud command uses the correct project (already set by gcloud config)
                           def policyOutput = sh(script: "gcloud iam service-accounts get-iam-policy ${TARGET_SERVICE_ACCOUNT_EMAIL} --project=${TARGET_GCP_PROJECT_ID}", returnStdout: true).trim()
                           echo "IAM Policy:"
                           echo "${policyOutput}"
                        }

                        // Terraform Init
                        sh 'terraform init -backend-config="bucket=${TARGET_TF_STATE_BUCKET}" -migrate-state'

                        // Terraform Validate
                        sh 'terraform validate'

                        // Terraform Plan
                        sh 'terraform plan -out=tfplan -var-file=environments/${DEPLOYMENT_ENV}.tfvars'
                        // Note: archiveArtifacts path is relative to workspace root by default,
                        // might need adjustment if running from within 'terraform' dir
                        archiveArtifacts artifacts: 'tfplan'

                        // Terraform Apply
                        // Manual approval step can be here or outside the dir block
                        input message: "Approve Terraform Apply to ${DEPLOYMENT_ENV} Environment?", ok: 'Proceed with Apply'

                        // Pass the correct variable file based on the selected environment
                        sh 'terraform apply tfplan' // Apply the saved plan file - NO -var-file HERE

                    } // End of dir('terraform') block
                } // End of withCredentials block
            } // End of steps block for 'Run GCP & Terraform Operations' stage
        } // End of 'Run GCP & Terraform Operations' stage
    } // End of top-level stages block
    post {
         // Add the clean up for the copied key file if you used that approach
         // The deleteDir step works relative to the current directory, or with absolute path
         // always {
         //    script {
         //        echo "Deleting persistent key file..."
         //        // If copied to workspace root
         //        // deleteDir(dir: "${WORKSPACE}/gcp_sa_key.json")
         //        // If copied inside the terraform dir
         //        // dir('terraform') { deleteDir(dir: 'gcp_sa_key.json') }
         //    }
         // }
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
