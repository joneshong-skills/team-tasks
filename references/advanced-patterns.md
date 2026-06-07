# Advanced Patterns — Team Tasks

進階使用模式與整合範例。

## Native Agent Teams 整合

### 啟用 Agent Teams

在 `~/.claude/settings.json` 加入：

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

### Agent Teams 提示詞範本

#### 研究型團隊（最安全的入門方式，不改 code）

```
建立一個 3 人 agent team 來研究 {topic}：
- Teammate 1: 從技術可行性角度分析
- Teammate 2: 從使用者體驗角度分析
- Teammate 3: 當魔鬼代言人，挑戰前兩位的觀點

不要寫任何程式碼，只做研究和分析。
每個 teammate 完成後在 task list 記錄結論。
```

#### 平行開發團隊

```
建立一個 agent team 來實作 {feature}：
- Teammate 1 (Sonnet): 後端 API ({api-desc})
- Teammate 2 (Sonnet): 前端元件 ({ui-desc})
- Teammate 3 (Sonnet): 測試 (等前兩位完成後再開始)

使用 Plan Approval — 每個 teammate 先寫計畫，我核准後再實作。
不同 teammate 負責不同檔案，避免衝突。
```

#### Code Review 團隊

```
建立一個 agent team 來 review 這個 PR：
- Teammate 1: 安全性審查（OWASP Top 10）
- Teammate 2: 效能分析（N+1 queries, memory leaks）
- Teammate 3: 測試覆蓋率檢查

每個 teammate 獨立審查，完成後互相 cross-review。
最後我會綜合結論。
```

### Hybrid 模式：maestro project + Agent Teams

結合持久化任務管理和即時協作：

```bash
# 1. 用 maestro project 規劃結構
~/.local/bin/maestro project create refactor-auth --mode dag -g "Refactor authentication to OAuth2"
~/.local/bin/maestro project add-task refactor-auth design -a planner --desc "Design OAuth2 flow"
~/.local/bin/maestro project add-task refactor-auth backend -a coder --deps "design" --desc "Implement OAuth2 provider"
~/.local/bin/maestro project add-task refactor-auth frontend -a ui-dev --deps "design" --desc "Update login UI"
~/.local/bin/maestro project add-task refactor-auth migrate -a coder --deps "backend" --desc "Write DB migration"
~/.local/bin/maestro project add-task refactor-auth test -a tester --deps "backend,frontend,migrate" --desc "E2E tests"

# 2. 查看依賴圖
~/.local/bin/maestro project graph refactor-auth
```

然後在 Claude Code 對話中使用 Agent Teams 執行：

```
我已用 maestro project 建好 refactor-auth 的任務結構。
請查看 ready 任務，建立 Agent Team 來執行。

完成每個任務後，執行以下指令回報：
~/.local/bin/maestro project update refactor-auth <task-id> done
~/.local/bin/maestro project result refactor-auth <task-id> "<summary>"
```

### Agent Teams 最佳實踐

1. **任務大小** — 每個 teammate 分配 5-6 個任務，不要太碎也不要太大
2. **避免檔案衝突** — 不同 teammate 負責不同檔案
3. **給足 context** — Teammates 不繼承 Lead 的對話歷史，spawn 時要給完整說明
4. **先研究再實作** — 新手先用研究型團隊（不改 code），熟悉後再平行開發
5. **Delegate Mode** — 按 Shift+Tab 讓 Lead 專注協調，避免自己也開始寫 code

### Subagents vs Agent Teams 決策

| 情境 | 推薦 |
|------|------|
| 單一聚焦任務，只需結果 | Subagents（Task tool） |
| 需要 agents 互相討論 | Agent Teams |
| 混合 Claude + Gemini + Codex | Custom Pipeline + Headless |
| 跨 session 追蹤進度 | Custom Pipeline（maestro project） |
| 即時平行開發 + 互相 review | Agent Teams |
| CI/CD 自動化整合 | Custom Pipeline + Headless |

---

## 多 Agent 自動派發（DAG + Headless）

透過 shell script 自動化 DAG 任務派發迴圈：

```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT="$1"

while true; do
    # 取得所有就緒任務
    READY=$(~/.local/bin/maestro project ready "$PROJECT" --json 2>/dev/null || echo "[]")
    COUNT=$(echo "$READY" | jq 'length')

    if [ "$COUNT" -eq 0 ]; then
        # 確認是否全部完成
        STATUS=$(~/.local/bin/maestro project status "$PROJECT" --json)
        PENDING=$(echo "$STATUS" | jq '[.tasks[] | select(.status != "done")] | length')
        if [ "$PENDING" -eq 0 ]; then
            echo "All tasks completed!"
            ~/.local/bin/maestro project log "$PROJECT"
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
        ~/.local/bin/maestro project update "$PROJECT" "$TASK_ID" in-progress

        # 派發給 claude headless（背景執行）
        (
            RESULT=$(claude -p "$TASK_DESC" \
                --allowedTools "Read,Edit,Bash" \
                --output-format json 2>/dev/null | jq -r '.result // "completed"')
            ~/.local/bin/maestro project result "$PROJECT" "$TASK_ID" "$RESULT"
            ~/.local/bin/maestro project update "$PROJECT" "$TASK_ID" done
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
            agy -p "$desc" 2>/dev/null
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
# 1. 建立辯論
~/.local/bin/maestro project create db-choice --mode debate -g "PostgreSQL vs MongoDB vs DynamoDB for our new service?"

# 2. 加入辯論者（含觀點角度）
~/.local/bin/maestro project add-debater db-choice relational -p "關聯式資料庫的優勢，ACID 特性，結構化查詢"
~/.local/bin/maestro project add-debater db-choice document -p "文件型資料庫的彈性，Schema-less 設計，水平擴展"
~/.local/bin/maestro project add-debater db-choice serverless -p "Serverless 資料庫的運維成本，自動擴展，按量計費"

# 3. 第一輪：各方陳述立場
~/.local/bin/maestro project round db-choice start

# 讓 Claude 代替各辯論者提交觀點
for debater in relational document serverless; do
    perspective=$(~/.local/bin/maestro project status db-choice --json | jq -r ".debaters[] | select(.id==\"$debater\") | .perspective")
    argument=$(claude -p "你是資料庫專家，從「${perspective}」的角度分析 PostgreSQL vs MongoDB vs DynamoDB，限 200 字" \
        --output-format json | jq -r '.result')
    ~/.local/bin/maestro project round db-choice submit -d "$debater" -t "$argument"
done

# 4. 交叉審查
~/.local/bin/maestro project round db-choice cross-review

# 5. 綜合結論
~/.local/bin/maestro project round db-choice synthesize
```

## Linear Pipeline：CI/CD 風格

依序執行：分析 → 實作 → 測試 → 文件 → 部署

```bash
~/.local/bin/maestro project create release-v2 --mode linear \
    -g "Release v2.0: refactor auth + add OAuth2" \
    -p "analyzer,implementer,tester,docs-writer,deployer"

# 每個階段完成後自動推進
~/.local/bin/maestro project update release-v2 analyzer done
~/.local/bin/maestro project result release-v2 analyzer "需要重構 auth middleware，新增 OAuth2 provider 支援"

~/.local/bin/maestro project next release-v2  # → implementer

~/.local/bin/maestro project update release-v2 implementer done
~/.local/bin/maestro project result release-v2 implementer "已新增 OAuth2Strategy class 和 /auth/oauth2/callback route"

# 以此類推...
```

## 錯誤處理與重試

任務失敗時的處理策略：

```bash
# 標記失敗
~/.local/bin/maestro project update my-feature backend failed

# 重置單一任務（改回 pending）
~/.local/bin/maestro project update my-feature backend pending

# 重置整個專案
~/.local/bin/maestro project reset my-feature

# 跳過非關鍵任務
~/.local/bin/maestro project update my-feature optional-feature skipped
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
~/.local/bin/maestro project update "$PROJECT" "$TASK_ID" done
notify "$PROJECT" "$TASK_ID" "done"
```

## JSON 輸出整合

多數指令支援 `--json` 旗標，方便程式化處理：

```bash
# 取得所有就緒任務的 ID 列表
~/.local/bin/maestro project ready my-feature --json | jq -r '.[].id'

# 取得專案完成度
~/.local/bin/maestro project status my-feature --json | jq '{
    total: (.tasks | length),
    done: [.tasks[] | select(.status == "done")] | length,
    progress: (([.tasks[] | select(.status == "done")] | length) * 100 / (.tasks | length))
}'

# 取得特定任務的結果
~/.local/bin/maestro project status my-feature --json | jq '.tasks[] | select(.id == "backend") | .result'
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
while [ "$(~/.local/bin/maestro project status design --json | jq -r '.tasks | all(.status == "done")')" != "true" ]; do
    sleep 5
done

# 啟動 backend 和 frontend
~/.local/bin/maestro project update backend api-impl in-progress &
~/.local/bin/maestro project update frontend ui-impl in-progress &
wait
```
