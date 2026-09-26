pipeline {
    agent any
    options {
        timeout(time: limit(), unit: 'MINUTES')
    }
    stages {
        stage('Build') {
            steps {
                sh 'make'
            }
        }
    }
}
