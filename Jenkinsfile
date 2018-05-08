pipeline {
    agent any
    stages {
        stage('build') {
            steps {
                sh 'python3 --version'
                sh 'echo "Hello World!"'
                sh '''
                    echo "Mulitlie shell steps works too"
                    ls -lah
                '''
            }
        }
    }
}
