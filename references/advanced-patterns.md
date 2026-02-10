# Advanced Patterns — Team Tasks

進階使用模式與整合範例。

## 多 Agent 自動派發（DAG + Headless）

透過 shell script 自動化 DAG 任務派發迴圈：

```bash
#!/usr/bin/env bash
set -euo pipefail

TM="python3 ~/.claude/skills/team-tasks/scripts/task_manager.py"
PROJECT="$1"

while true; do
    # 取得所有就緒任務
    READY=$($TM ready "$PROJECT" --json 2>/dev/null || echo "[]")
    COUNT=$(echo "$READY" | jq 'length')

    if [ "$COUNT" -eq 0 ]; then
        # 確認是否全部完成
        STATUS=$($TM status "$PROJECT" --json)
        PENDING=$(echo "$STATUS" | jq '[.tasks[] | select(.status != "done")] | length')
        if [ "$PENDING" -eq 0 ]; then
            echo "All tasks completed!"
            $TM log "$PROJECT"
            break
        fi
        echo "Waiting for in-progress tasks..."
        sleep 5
        continue
    fi

    # 平行派發每個就緒任務
    echo "$READY" | jq -c '.[]' | while IFS= read -r task; do
        TASK_ID=$(echo "$task" | jq -r '.id')
        TASK_DESC=$(echo "$task" | jq -r '.description // .id')
        TASK_AGENT=$(echo "$task" | jq -r '.agent // "default"')

        echo "Dispatching: $TASK_ID → $TASK_AGENT"
        $TM update "$PROJECT" "$TASK_ID" in-progress

        # 派發給 claude headless（背景執行）
        (
            RESULT=$(claude -p "$TASK_DESC" \
                --allowedTools "Read,Edit,Bash" \
                --output-format json 2>/dev/null | jq -r '.result // "completed"')
            $TM result "$PROJECT" "$TASK_ID" "$RESULT"
            $TM update "$PROJECT" "$TASK_ID" done
        ) &
    done

    # 等待本批次完成
    wait
done
```

## 混合 Agent 派發（Claude + Gemini + Codex）

根據任務的 agent 欄位決定要派發給哪個 CLI：

```bash
dispatch_task() {
    local agent="$1" desc="$2"
    case "$agent" in
        claude|code-agent)
            claude -p "$desc" --allowedTools "Read,Edit,Bash" --output-format json | jq -r '.result'
            ;;
        gemini|review-agent)
            gemini -p "$desc" 2>/dev/null
            ;;
        codex|refactor-agent)
            codex exec "$desc" --full-auto 2>/dev/null
            ;;
        *)
            claude -p "$desc" --output-format json | jq -r '.result'
            ;;
    esac
}
```

## Debate 模式：架構決策流程

完整的三方辯論工作流，用於技術選型：

```bash
TM="python3 ~/.claude/skills/team-tasks/scripts/task_manager.py"

# 1. 建立辯論
$TM init db-choice --mode debate -g "PostgreSQL vs MongoDB vs DynamoDB for our new service?"

# 2. 加入辯論者（含觀點角度）
$TM add-debater db-choice relational -p "關聯式資料庫的優勢，ACID 特性，結構化查詢"
$TM add-debater db-choice document -p "文件型資料庫的彈性，Schema-less 設計，水平擴展"
$TM add-debater db-choice serverless -p "Serverless 資料庫的運維成本，自動擴展，按量計費"

# 3. 第一輪：各方陳述立場
$TM round db-choice start

# 讓 Claude 代替各辯論者提交觀點
for debater in relational document serverless; do
    perspective=$($TM status db-choice --json | jq -r ".debaters[] | select(.id==\"$debater\") | .perspective")
    argument=$(claude -p "你是資料庫專家，從「${perspective}」的角度分析 PostgreSQL vs MongoDB vs DynamoDB，限 200 字" \
        --output-format json | jq -r '.result')
    $TM round db-choice submit -d "$debater" -t "$argument"
done

# 4. 交叉審查
$TM round db-choice cross-review

# 5. 綜合結論
$TM round db-choice synthesize
```

## Linear Pipeline：CI/CD 風格

依序執行：分析 → 實作 → 測試 → 文件 → 部署

```bash
TM="python3 ~/.claude/skills/team-tasks/scripts/task_manager.py"

$TM init release-v2 --mode linear \
    -g "Release v2.0: refactor auth + add OAuth2" \
    -p "analyzer,implementer,tester,docs-writer,deployer"

# 每個階段完成後自動推進
$TM update release-v2 analyzer done
$TM result release-v2 analyzer "需要重構 auth middleware，新增 OAuth2 provider 支援"

$TM next release-v2  # → implementer

$TM update release-v2 implementer done
$TM result release-v2 implementer "已新增 OAuth2Strategy class 和 /auth/oauth2/callback route"

# 以此類推...
```

## 錯誤處理與重試

任務失敗時的處理策略：

```bash
TM="python3 ~/.claude/skills/team-tasks/scripts/task_manager.py"

# 標記失敗
$TM update my-feature backend failed

# 重置單一任務（改回 pending）
$TM update my-feature backend pending

# 重置整個專案
$TM reset my-feature

# 跳過非關鍵任務
$TM update my-feature optional-feature skipped
```

## 搭配 OpenClaw 通知

任務狀態變更時發送 Telegram 通知：

```bash
notify() {
    local project="$1" task="$2" status="$3"
    openclaw message send \
        --channel telegram \
        --target "${OPENCLAW_TARGET:--5149469295}" \
        --message "📋 $project/$task → $status"
}

# 在派發迴圈中使用
$TM update "$PROJECT" "$TASK_ID" done
notify "$PROJECT" "$TASK_ID" "done"
```

## JSON 輸出整合

多數指令支援 `--json` 旗標，方便程式化處理：

```bash
# 取得所有就緒任務的 ID 列表
$TM ready my-feature --json | jq -r '.[].id'

# 取得專案完成度
$TM status my-feature --json | jq '{
    total: (.tasks | length),
    done: [.tasks[] | select(.status == "done")] | length,
    progress: (([.tasks[] | select(.status == "done")] | length) * 100 / (.tasks | length))
}'

# 取得特定任務的結果
$TM status my-feature --json | jq '.tasks[] | select(.id == "backend") | .result'
```

## 大型專案拆分策略

當專案超過 10 個任務時，考慮拆分成子專案：

```
main-project/
├── design (DAG) → 產出 API spec
├── backend (DAG) → 依賴 design 的結果
├── frontend (DAG) → 依賴 design 的結果
└── integration (Linear) → 整合測試 pipeline
```

每個子專案獨立管理，用 shell script 串接：

```bash
# 等待 design 專案完成
while [ "$($TM status design --json | jq -r '.tasks | all(.status == "done")')" != "true" ]; do
    sleep 5
done

# 啟動 backend 和 frontend
$TM update backend api-impl in-progress &
$TM update frontend ui-impl in-progress &
wait
```
