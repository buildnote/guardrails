pipeline {
  agent any
  stages {
    stage(env.STAGE_NAME) {
      options {
        timeout(time: 20, unit: 'MINUTES')
      }
      parallel {
        stage('Unit') {
          steps {
            sh './gradlew test'
          }
        }
      }
    }
  }
}
