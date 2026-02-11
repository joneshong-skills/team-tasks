---
name: team-tasks
description: This skill should be used when the user asks to "coordinate agents", "manage team tasks", "create a pipeline", "dispatch work to agents", "run parallel tasks", "start a debate", "multi-agent workflow", or discusses task orchestration, agent teams, pipeline coordination, DAG execution, or debate-style review.
version: 0.1.0
tools: Read, Bash, Edit
argument-hint: "<project-name> [--mode linear|dag|debate]"
---

# Team Tasks — 多 Agent 任務協調

透過 JSON 任務檔協調多 Agent 開發流程。支援三種模式：依序 pipeline、依賴圖平行派發、多方辯論。

## 快速開始

CLI 路徑（所有指令使用此前綴）：

```bash
TM="python3 ~/.claude/skills/team-tasks/scripts/task_manager.py"
```

資料目錄：`~/.claude/data/team-tasks/`（可透過 `TEAM_TASKS_DIR` 環境變數覆寫）

## 三種模式

### Linear（依序 Pipeline）

適用：Bug 修復、逐步驗證、固定流程。

```bash
# 建立 pipeline
$TM init my-api --mode linear \
  -g "建立 REST API 並測試" \
  -p "code-agent,test-agent,docs-agent"

# 查看下一階段
$TM next my-api

# 標記完成 → 自動推進到下一階段
$TM update my-api code-agent done
$TM result my-api code-agent "API 實作完成，含 CRUD endpoints"
```

### DAG（依賴圖平行執行）

適用：大型功能、多模組並行、複雜依賴鏈。

```bash
# 建立專案
$TM init my-feature --mode dag -g "建立使用者系統"

# 新增任務（含依賴關係）
$TM add my-feature design -a planner --desc "設計 API 規格"
$TM add my-feature backend -a code-agent --deps "design" --desc "實作後端"
$TM add my-feature frontend -a ui-agent --deps "design" --desc "實作前端"
$TM add my-feature e2e-test -a test-agent --deps "backend,frontend" --desc "E2E 測試"

# 查看可派發任務
$TM ready my-feature

# 派發完成後，依賴任務自動解鎖
$TM update my-feature design done
$TM ready my-feature  # → backend + frontend 同時可派發
```

### Debate（多方辯論）

適用：架構決策、Code Review、技術選型。

```bash
# 建立辯論
$TM init arch-review --mode debate -g "微服務 vs 單體架構？"

# 加入辯論者
$TM add-debater arch-review security-expert -p "資安角度"
$TM add-debater arch-review perf-expert -p "效能角度"
$TM add-debater arch-review dx-expert -p "開發體驗角度"

# 開始辯論
$TM round arch-review start

# 提交各方觀點
$TM round arch-review submit -d security-expert -t "微服務隔離性更好..."
$TM round arch-review submit -d perf-expert -t "單體減少網路開銷..."

# 交叉審查 → 綜合結論
$TM round arch-review cross-review
$TM round arch-review synthesize
```

## 指令參考

| 指令 | 模式 | 說明 |
|------|------|------|
| `init <project>` | 全部 | 建立專案 (`--mode linear\|dag\|debate`) |
| `add <project> <task>` | DAG | 新增任務 (`--deps`, `--agent`, `--desc`) |
| `add-debater <project> <id>` | Debate | 新增辯論者 (`--perspective`) |
| `status <project>` | 全部 | 顯示專案狀態 |
| `next <project>` | Linear | 取得下一階段 |
| `ready <project>` | DAG | 列出可派發任務 |
| `update <project> <task> <status>` | Linear/DAG | 更新狀態 |
| `result <project> <task> <text>` | Linear/DAG | 記錄結果 |
| `round <project> <action>` | Debate | 管理辯論 (start/submit/cross-review/synthesize/status) |
| `graph <project>` | 全部 | 視覺化依賴 |
| `log <project>` | Linear/DAG | 顯示執行紀錄 |
| `reset <project>` | 全部 | 重置所有狀態 |
| `list` | — | 列出所有專案 |

狀態值：`pending` → `in-progress` → `done` / `failed` / `skipped`

## 調度模式

### 手動調度

直接在 Claude Code 對話中執行 `$TM` 指令，根據結果決定下一步。

### 搭配 Headless Agent

透過 `claude -p` 或 `gemini -p` 派發任務給獨立的 headless agent：

```bash
# 取得待辦任務
task=$($TM ready my-feature --json | jq -r '.[0].id')
desc=$($TM ready my-feature --json | jq -r '.[0].description')

# 派發給 claude headless
$TM update my-feature "$task" in-progress
result=$(claude -p "$desc" --cwd /path/to/project --allowedTools "Read,Edit,Bash" --output-format json | jq -r '.result')
$TM result my-feature "$task" "$result"
$TM update my-feature "$task" done
```

### 搭配 OpenClaw

透過 OpenClaw 發送任務到 Telegram 群組中的 Agent：

```bash
task=$($TM next my-api --json | jq -r '.id')
openclaw message send --channel telegram --target <group-id> \
  --message "請執行任務: $task"
```

## 工作流範例

### 典型 DAG 工作流

```
1. $TM init → 建立專案
2. $TM add  → 定義所有任務和依賴
3. $TM graph → 確認依賴結構
4. LOOP:
   a. $TM ready → 取得可派發任務
   b. 派發給 agent（手動/headless/openclaw）
   c. $TM update → 標記 in-progress
   d. 等待結果
   e. $TM result → 記錄結果
   f. $TM update → 標記 done
   g. 回到 4a 直到全部完成
5. $TM log → 查看完整紀錄
```

## Additional Resources

### Reference Files

- **`references/advanced-patterns.md`** — 進階使用模式與 agent 派發整合範例

### Example Files

- **`examples/linear-demo.sh`** — Linear 模式完整範例
- **`examples/dag-demo.sh`** — DAG 模式完整範例
