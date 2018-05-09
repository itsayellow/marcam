#!/usr/bin/env groovy
pipeline {
    agent any

    environment {
        PATH = '/Users/mclapp/git/projects/bin/mac:/Users/mclapp/git/projects/bin:/Users/mclapp/.Bin:/usr/local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/sbin'
    }
    stages {
        stage('Build') {
            steps {
                sh 'make app'
            }
        }
        stage('Deploy') {
            steps {
                sh 'make dmg'
            }
            post {
                success {
                    archiveArtifacts 'dist/Marcam.dmg'
                }
            }
        }
    }
}
