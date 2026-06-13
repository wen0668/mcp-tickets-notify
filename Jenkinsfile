pipeline {
    agent any

    parameters {
        string( name: 'DATE',         defaultValue: '',
                description: '出发日期，如 2026-06-21（留空则默认明天）' )
        string( name: 'FROM_STATION', defaultValue: '茂名',
                description: '出发站，如 茂名、广州南' )
        string( name: 'TO_STATION',   defaultValue: '广州南',
                description: '到达站，如 广州南、深圳北' )
        string( name: 'AFTER_TIME',   defaultValue: '',
                description: '只显示该时间后的车次，如 18:30（留空=全部）' )
        string( name: 'SEAT_TYPE',    defaultValue: '',
                description: '只显示指定座级，如 二等座、一等座（留空=全部）' )
        string( name: 'HOST',         defaultValue: 'http://192.168.0.4:31234',
                description: 'MCP 12306 服务地址' )
        string( name: 'WECOM_WEBHOOK', defaultValue: '',
                description: '企业微信机器人 Webhook URL（留空=不推送）' )
    }

    environment {
        RESULT_FILE = 'ticket_result.txt'
    }

    stages {

        // ── 1. Query 12306 ──────────────────────────────────
        stage('Query Tickets') {
            steps {
                script {
                    def queryDate = params.DATE ?: sh(
                        script: "date -v+1d '+%Y-%m-%d' 2>/dev/null || date -d '+1 day' '+%Y-%m-%d'",
                        returnStdout: true
                    ).trim()

                    def cmd = "python3 query_tickets.py" +
                              " --host '${params.HOST}'" +
                              " --date '${queryDate}'" +
                              " --from-station '${params.FROM_STATION}'" +
                              " --to-station '${params.TO_STATION}'"

                    if (params.AFTER_TIME) { cmd += " --after-time '${params.AFTER_TIME}'" }
                    if (params.SEAT_TYPE)  { cmd += " --seat-type '${params.SEAT_TYPE}'" }

                    echo "Running: ${cmd}"
                    sh "${cmd} | tee ${RESULT_FILE}"
                }
            }
        }

        // ── 2. Send to WeChat Work ──────────────────────────
        stage('Notify WeChat') {
            when { expression { params.WECOM_WEBHOOK?.trim() } }
            steps {
                script {
                    def queryDate = params.DATE ?: sh(script: "date +%Y-%m-%d", returnStdout: true).trim()
                    def result   = readFile(RESULT_FILE).trim()
                    def summary  = result.length() > 2000 ? result.substring(0, 1997) + "..." : result

                    def filterInfo = ""
                    if (params.AFTER_TIME) { filterInfo += " ⏰${params.AFTER_TIME}后" }
                    if (params.SEAT_TYPE)  { filterInfo += " 💺${params.SEAT_TYPE}" }

                    def markdown = """\
                        ## 🚄 12306 余票查询
                        **${params.FROM_STATION} → ${params.TO_STATION}** | ${queryDate}${filterInfo}
                        ---
                        ```
                        ${summary}
                        ```
                        > 下次查询: [Jenkins](${env.BUILD_URL})
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
