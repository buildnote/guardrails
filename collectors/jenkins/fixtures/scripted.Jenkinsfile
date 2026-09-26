@Library('company-shared@main') _

node('linux') {
    stage('Build') {
        withCredentials([string(credentialsId: 'npm-token', variable: 'NPM_TOKEN')]) {
            sh 'make'
        }
    }
}
