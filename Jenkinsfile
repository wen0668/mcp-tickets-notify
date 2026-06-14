pipeline {
    agent any

    parameters {
        string( name: 'DATE',          defaultValue: '',
                description: '出发日期，如 2026-06-21（留空则默认明天）' )
        choice( name: 'FROM_STATION',  choices: ['广州南','茂名南','茂名','广州','广州白云'],
                description: '出发站' )
        choice( name: 'TO_STATION',    choices: ['茂名','茂名南','广州南','广州','广州白云'],
                description: '到达站' )
        string( name: 'AFTER_TIME',    defaultValue: '',
                description: '只显示该时间后的车次，如 18:30（留空=全部）' )
        choice( name: 'SEAT_TYPE',     choices: ['全部','二等座','一等座','商务座','硬座','硬卧','软卧','无座'],
                description: '只显示指定座级（全部=不过滤）' )
        choice( name: 'SHOW_MODE',     choices: ['仅显示有票','显示全部含无票'],
                description: '显示模式' )
        string( name: 'HOST',          defaultValue: 'http://192.168.0.4:31234',
                description: 'MCP 12306 服务地址' )
        string( name: 'REMOTE_HOST',   defaultValue: '192.168.0.88',
                description: '执行查询的远程主机 IP' )
        string( name: 'REMOTE_USER',   defaultValue: 'liwenzhong',
                description: 'SSH 登录用户名' )
        string( name: 'WECOM_WEBHOOK', defaultValue: '',
                description: '企业微信机器人 Webhook URL（留空=不推送）' )
    }

    environment {
        GIT_REPO    = 'https://github.com/wen0668/mcp-tickets-notify.git'
        GIT_BRANCH  = 'main'
        RESULT_FILE = 'ticket_result.html'
        SSH_OPTS    = '-o StrictHostKeyChecking=no -o ConnectTimeout=10'
    }

    stages {

        // ── 0. Checkout ──────────────────────────────────────
        stage('Checkout') {
            steps {
                checkout([$class: 'GitSCM',
                    branches: [[name: "${GIT_BRANCH}"]],
                    userRemoteConfigs: [[url: "${GIT_REPO}"]]
                ])
            }
        }

        // ── 1. Query via SSH to remote host ──────────────────
        stage('Query Tickets') {
            steps {
                script {
                    def rhost    = "${params.REMOTE_USER}@${params.REMOTE_HOST}"
                    def queryDate = params.DATE ?: sh(
                        script: "date -v+1d '+%Y-%m-%d' 2>/dev/null || date -d '+1 day' '+%Y-%m-%d'",
                        returnStdout: true
                    ).trim()

                    def cmd = "python3 /tmp/query_tickets.py" +
                              " --host '${params.HOST}'" +
                              " --date '${queryDate}'" +
                              " --from-station '${params.FROM_STATION}'" +
                              " --to-station '${params.TO_STATION}'" +
                              " --timeout 20"

                    if (params.AFTER_TIME) { cmd += " --after-time '${params.AFTER_TIME}'" }
                    if (params.SEAT_TYPE && params.SEAT_TYPE != '全部') { cmd += " --seat-type '${params.SEAT_TYPE}'" }
                    if (params.SHOW_MODE == '显示全部含无票') { cmd += " --show-all" }

                    echo "Querying: ${cmd}"

                    sh """
                        scp ${SSH_OPTS} query_tickets.py '${rhost}':/tmp/query_tickets.py
                        ssh ${SSH_OPTS} '${rhost}' 'export LANG=zh_CN.UTF-8 PYTHONIOENCODING=utf-8; ${cmd}' > /tmp/raw.txt

                        # Wrap in HTML with UTF-8 charset so browser renders Chinese correctly
                        echo '<!DOCTYPE html><html><head><meta charset="utf-8"><style>pre{font-family:monospace}</style></head><body><pre>' > ${RESULT_FILE}
                        cat /tmp/raw.txt >> ${RESULT_FILE}
                        echo '</pre></body></html>' >> ${RESULT_FILE}
                    """
                }
            }
        }

        // ── 2. Send to WeChat Work ───────────────────────────
        stage('Notify WeChat') {
            when { expression { params.WECOM_WEBHOOK?.trim() } }
            steps {
                script {
                    def queryDate = params.DATE ?: sh(script: "date +%Y-%m-%d", returnStdout: true).trim()
                    def result    = readFile('/tmp/raw.txt').trim()
                    def summary   = result.length() > 2000 ? result.substring(0, 1997) + "..." : result

                    def filterInfo = ""
                    if (params.AFTER_TIME) { filterInfo += " ⏰${params.AFTER_TIME}后" }
                    if (params.SEAT_TYPE && params.SEAT_TYPE != '全部') { filterInfo += " 💺${params.SEAT_TYPE}" }

                    def markdown = """\
                        ## 🚄 12306 余票查询
                        **${params.FROM_STATION} → ${params.TO_STATION}** | ${queryDate}${filterInfo}
                        ---
                        ```
                        ${summary}
                        ```
                        > 查询节点: ${params.REMOTE_HOST} | [Jenkins](${env.BUILD_URL})
                        """.stripIndent()

                    def payload = groovy.json.JsonOutput.toJson([
                        msgtype: "markdown",
                        markdown: [content: markdown]
                    ])

                    sh """
                        curl -s -X POST '${params.WECOM_WEBHOOK}' \
                            -H 'Content-Type: application/json' \
                            -d '${payload}'
                    """
                    echo "→ WeChat notification sent"
                }
            }
        }

    }

    post {
        always {
            archiveArtifacts artifacts: RESULT_FILE, fingerprint: false
        }
    }
}
