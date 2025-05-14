# Local Jenkins Setup

## Prerequisites
- Docker and Docker Compose installed
- GCP service account key (sa-key-1.json)

## Setup Steps

1. Copy your service account key:
```bash
cp /path/to/sa-key-1.json ./sa-key-1.json
```

2. Start Jenkins:
```bash
docker-compose up -d
```

3. Get the initial admin password:
```bash
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword
```

4. Access Jenkins UI:
- Open http://localhost:8080
- Enter the initial admin password
- Install suggested plugins
- Create admin user

5. Configure Jenkins:

a. Install required plugins:
- Terraform
- Google Cloud SDK
- Credentials Binding

b. Configure tools:
- Add Terraform installation in "Manage Jenkins" > "Tools"
  - Name: Terraform-v1.11.3
  - Install automatically: Check
  - Version: 1.11.3

c. Add credentials:
- Go to "Manage Jenkins" > "Credentials" > "System" > "Global credentials"
- Add new credentials
  - Kind: Secret file
  - ID: gcp-sa-dev
  - File: Upload sa-key-1.json

6. Create test pipeline:
- New Item > Pipeline
- Configure pipeline:
  - Definition: Pipeline script from SCM
  - SCM: Git
  - Repository URL: Your repository URL
  - Branch: */dev
  - Script Path: Jenkinsfile

## Testing
1. Run the pipeline
2. Check logs for any issues
3. Verify Terraform initialization works

## Cleanup
```bash
docker-compose down -v
``` 