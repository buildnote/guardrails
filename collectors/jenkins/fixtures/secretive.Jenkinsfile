pipeline {
    agent any
    environment {
        API_KEY = '%s'
    }
    stages {
        stage('Deploy') {
            steps {
                withCredentials([string(credentialsId: 'deploy-token', variable: 'TOKEN')]) {
                    sh 'curl -H "Authorization: $TOKEN" https://company.test'
                }
            }
        }
        stage('Notify') {
            steps {
                slackSend(channel: '#builds', token: '%s')
            }
        }
    }
}
