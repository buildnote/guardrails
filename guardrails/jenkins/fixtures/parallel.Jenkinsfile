pipeline {
    agent any
    stages {
        stage('Verify') {
            options {
                timeout(time: 20, unit: 'MINUTES')
            }
            parallel {
                stage('Unit') {
                    steps {
                        sh 'make unit'
                    }
                }
            }
        }
    }
}
