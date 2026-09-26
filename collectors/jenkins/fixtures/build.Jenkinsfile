@Library('company-pipeline@1.4.2') _

pipeline {
    agent {
        docker {
            image 'maven:3.9.6'
        }
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
    }

    triggers {
        cron('H 4 * * 1-5')
        pollSCM('H/15 * * * *')
    }

    tools {
        jdk 'temurin-21'
        maven 'M3'
    }

    environment {
        GRADLE_OPTS = '-Dorg.gradle.daemon=false'
        SONAR_TOKEN = credentials('sonar-token')
    }

    stages {
        stage('Build') {
            steps {
                checkout scm
                sh './gradlew build'
            }
        }

        stage('Publish') {
            agent { label 'linux' }
            when {
                branch 'main'
            }
            options {
                timeout(time: 10, unit: 'MINUTES')
            }
            steps {
                withCredentials([usernamePassword(credentialsId: 'registry', usernameVariable: 'U', passwordVariable: 'P')]) {
                    sh './gradlew publish'
                }
            }
        }
    }
}
