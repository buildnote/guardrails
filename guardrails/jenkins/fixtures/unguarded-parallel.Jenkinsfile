pipeline {
    agent any
    stages {
        stage('Verify') {
            parallel {
                stage('Unit') {
                    options {
                        timeout(time: 5, unit: 'MINUTES')
                    }
                    steps {
                        sh 'make unit'
                    }
                }
                stage('Integration') {
                    steps {
                        sh 'make integration'
                    }
                }
            }
        }
    }
}
