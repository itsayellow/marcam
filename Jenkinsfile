#!/usr/bin/env groovy
pipeline {
    agent any

    environment {
        PATH = '/Users/mclapp/git/projects/bin/mac:/Users/mclapp/git/projects/bin:/Users/mclapp/.Bin:/usr/local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/sbin'
    }
    stages {
        stage('Build') {
            steps {
                sh 'make clean'
                sh 'make app'
            }
        }
        stage('Test') {
            steps {
                sh 'make tests'
            }
            /*
            post {
                always {
                    junit 'test-reports/results.xml'
                }
            }
            */
        }
        stage('Deploy') {
            steps {
                sh 'make dmg'
            }
            post {
                success {
                    sh 'cp dist/Marcam.dmg "/Users/mclapp/Google Drive/Marcam/Marcam Mac Latest.dmg"'
                    archiveArtifacts 'dist/Marcam.dmg'
                }
            }
        }
    }
}
