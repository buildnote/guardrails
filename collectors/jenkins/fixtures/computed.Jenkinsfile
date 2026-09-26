pipeline {
  agent any
  stages {
    stage('Build') {
      options {
        timeout(time: limit(), unit: 'MINUTES')
      }
      steps {
        sh './gradlew build'
      }
    }
  }
}
