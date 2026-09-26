@Library(['company-shared@%s', 'company-legacy'])
@Library("company-branchy@${env.BRANCH_NAME}") _

pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                library 'company-deploy@main'
                sh 'make'
            }
        }
    }
}
