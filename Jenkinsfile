pipeline {
    agent any
    stages {
        stage('Checkout Code') {
            steps {
                checkout scm
            }
        }
        stage('Hello World') {
            steps {
                echo 'Hello from Jenkins Dev Pipeline!'
                sh 'echo "Running a shell command"'
            }
        }
    }
}
