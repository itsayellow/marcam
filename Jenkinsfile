#!/usr/bin/env groovy
pipeline {
    agent any

    environment {
        PATH = '/Users/mclapp/git/projects/bin/mac:/Users/mclapp/git/projects/bin:/Users/mclapp/.Bin:/usr/local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/sbin'
    }
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
