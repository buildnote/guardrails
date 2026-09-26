pipeline {
    agent any
    stages {
        // a comment with a stray { brace in it
        stage('Build') {
            steps {
                sh 'echo } not a close brace'
                sh """
                    for file in *; do
                        echo ${file}
                    done
                """
                echo 'done'
            }
        }
    }
}
