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
                stage('Integration') {
                    stages {
                        stage('Provision') {
                            steps {
                                sh 'make provision'
                            }
                        }
                    }
                }
            }
        }
    }
}
