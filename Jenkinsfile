pipeline {
    agent { docker { image 'python:3.6.5' } }
    stages {
        stage('build') {
            steps {
                sh 'python --version'
                sh 'echo "Hello World!"'
                sh '''
                    echo "Mulitlie shell steps works too"
                    ls -lah
                '''
            }
        }
    }
}
