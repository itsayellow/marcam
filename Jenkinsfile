#!/usr/bin/env groovy
/*
Jenkins plugins added: Bitbucket Plugin, Warnings Plugin,
    Static Analysis Utilities,
*/
pipeline {
    agent any

    options {
        buildDiscarder(logRotator(daysToKeepStr: '30'))
    }

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
        stage('Pylint') {
            steps {
                sh 'make pylint_jenkins | tee pylint.log'
                // if any errors in pylint.log, make exit(1)
                sh '! grep -q \'\\[E\' pylint.log'
            }
            post {
                always {
                    step([$class: 'WarningsPublisher', parserConfigurations: [[
                        parserName: 'pylint',
                        pattern: 'pylint.log'
                    ]]])
                    /* theoretically the following works on Warnings v5.0
                    recordIssues enabledForFailure: true,
                        tools: [[tool: [$class: 'PyLint']]]
                    */
                }
                failure {
                    echo "Pylint errors, failure:"
                    sh 'grep \'\\[E\' pylint.log'
                }
            }
        }
        stage('Test') {
            steps {
                //sh 'make pylint_errors_jenkins'
                sh 'make tests'
            }
            post {
                always {
                    junit 'pytest_results.xml'
                }
            }
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
