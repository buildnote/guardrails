pipeline {
    agent none
    stages {
        stage('Hours') {
            options {
                timeout(time: 2, unit: 'HOURS')
            }
            steps {
                sh 'make slow'
            }
        }
        stage('Seconds') {
            options {
                timeout(time: 90, unit: 'SECONDS')
            }
            steps {
                sh 'make quick'
            }
        }
        stage('Default unit') {
            options {
                timeout(time: 45)
            }
            steps {
                sh 'make'
            }
        }
        stage('Chosen at runtime') {
            options {
                timeout(time: params.LIMIT, unit: 'MINUTES')
            }
            steps {
                sh 'make'
            }
        }
    }
}
