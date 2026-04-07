---
name: team-tasks
description: This skill should be used when the user asks to "coordinate agents", "manage team tasks", "create a pipeline", "dispatch work to agents", "run parallel tasks", "start a debate", "multi-agent workflow", "agent teams", "create a team", "spawn teammates", or discusses task orchestration, agent teams, pipeline coordination, DAG execution, or debate-style review.
version: 0.2.1
tools: Read, Bash, Edit
argument-hint: "<project-name> [--engine native|custom] [--mode linear|dag|debate]"
---

# Team Tasks — 多 Agent 任務協調

支援兩種引擎：Claude Code **內建 Agent Teams**（即時協作）和**自訂 Pipeline**（持久化任務管理）。

## Step 0 — 選擇引擎

```
使用者需求
    │
    ├─ 需要多個 agent 即時討論、互相挑戰、自主協調？
    │   └─ → Native Agent Teams
    │
    ├─ 需要持久化任務紀錄、跨 session 追蹤、混合 CLI 派發？
    │   └─ → Custom Pipeline（task_manager.py）
    │
    ├─ 需要結合兩者？（持久追蹤 + 即時協作）
    │   └─ → Hybrid 模式
    │
    └─ 不確定？看下面的對照表
```

| 面向 | Native Agent Teams | Custom Pipeline |
|------|-------------------|-----------------|
| **溝通** | Teammates 互相直接通訊 | 透過 JSON 檔間接傳遞 |
| **協調** | 自動認領任務、即時信箱 | 手動/腳本派發 |
| **持久化** | Session 結束即消失 | JSON 檔永久保存 |
| **混合 CLI** | 僅 Claude Code | Claude + Gemini + Codex（headless 或 interactive） |
| **Token 成本** | 較高（每 teammate 獨立實例） | 較低（headless 單次呼叫）或中等（interactive 多輪） |
| **可視化** | tmux/iTerm2 分割面板 | ASCII 依賴圖 |
| **Resume** | 不支援（實驗性限制） | 支援（JSON 狀態檔） |
| **適合** | 研究、辯論、並行開發 | CI/CD pipeline、跨 session 追蹤 |

---

## Engine A — Native Agent Teams（內建）

### 前置條件

啟用實驗性功能（二擇一）：

**settings.json**（推薦）：
```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

**Shell 環境變數**：
```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

### 檢查是否已啟用

```bash
# 確認環境變數
echo $CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS
# 或檢查 settings.json
cat ~/.claude/settings.json | ~/.local/bin/python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('env',{}).get('CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS','未設定'))"
```

### 快速開始

啟用後，用自然語言描述團隊結構即可：

```
建立一個 agent team 來開發使用者系統：
- 一個 teammate 負責後端 API
- 一個 teammate 負責前端 React 元件
- 一個 teammate 負責寫測試
```

也可以指定模型和數量：
```
Create a team with 3 teammates using Sonnet.
Teammate 1: API design. Teammate 2: implementation. Teammate 3: code review.
```

### 架構概覽

| 元件 | 角色 |
|------|------|
| **Team Lead** | 主 session，建立團隊、產生 teammates、協調工作 |
| **Teammates** | 獨立 Claude Code 實例，各自處理分配的任務 |
| **Task List** | 共享任務清單，支援依賴追蹤，teammates 可自行認領 |
| **Mailbox** | agents 之間的直接通訊系統 |

解鎖的工具：`TeamCreate`、`TaskCreate`、`TaskUpdate`、`TaskList`、`SendMessage`

### 顯示模式

| 模式 | 設定 | 說明 |
|------|------|------|
| **In-process** | `"teammateMode": "in-process"` | 同一終端，Shift+Up/Down 切換 |
| **Split panes** | `"teammateMode": "split"` | 每個 teammate 獨立 tmux/iTerm2 面板 |

CLI 啟動時指定：`claude --teammate-mode in-process`

### 關鍵功能

- **Plan Approval** — 要求 teammates 先寫計畫，Lead 核准後才改 code
- **Delegate Mode** — 按 **Shift+Tab** 讓 Lead 只協調不寫 code
- **Direct Messaging** — 對任何 teammate 直接發訊息
- **Task Dependencies** — 任務可設定依賴，blocked 任務自動解鎖
- **Self-Claiming** — teammates 完成後自動認領下一個任務
- **Quality Gate Hooks** — `TeammateIdle` / `TaskCompleted` hooks

### 最佳使用場景

1. **研究與審查** — 多 teammates 同時調查不同面向，互相挑戰
2. **新模組開發** — 每人負責一個獨立模組
3. **除錯：競爭假設** — 平行測試不同理論
4. **跨層協調** — 前端/後端/測試各由不同 teammate 負責
5. **平行 Code Review** — 安全性/效能/測試各一個 reviewer

### 注意事項

- 實驗性功能，`/resume` 和 `/rewind` 不支援 in-process teammates
- 一個 session 只能一個 team，不支援巢狀
- Token 成本隨 teammate 數量顯著增加
- VS Code Terminal / Windows Terminal / Ghostty 不支援 split panes

---

## Engine B — Custom Pipeline（task_manager.py）

### 快速開始

CLI 路徑（所有指令使用此前綴）：

```bash
TM="~/.local/bin/python3 ~/.claude/skills/team-tasks/scripts/task_manager.py"
```

> **zsh 注意事項**：使用 `$TM` 時務必加雙引號 `"$TM"` 以避免 word splitting 問題。
> 或直接用完整路徑 `~/.local/bin/python3 ~/.claude/skills/team-tasks/scripts/task_manager.py`。

資料目錄：`~/.claude/data/team-tasks/`（可透過 `TEAM_TASKS_DIR` 環境變數覆寫）

### 三種模式

### Linear（依序 Pipeline）

適用：Bug 修復、逐步驗證、固定流程。

```bash
# 建立 pipeline
"$TM" init my-api --mode linear \
  -g "建立 REST API 並測試" \
  -p "code-agent,test-agent,docs-agent"

# 查看下一階段
"$TM" next my-api

# 標記完成 → 自動推進到下一階段
"$TM" update my-api code-agent done
"$TM" result my-api code-agent "API 實作完成，含 CRUD endpoints"
```

### DAG（依賴圖平行執行）

適用：大型功能、多模組並行、複雜依賴鏈。

```bash
# 建立專案
"$TM" init my-feature --mode dag -g "建立使用者系統"

# 新增任務（含依賴關係）
"$TM" add my-feature design -a planner --desc "設計 API 規格"
"$TM" add my-feature backend -a code-agent --deps "design" --desc "實作後端"
"$TM" add my-feature frontend -a ui-agent --deps "design" --desc "實作前端"
"$TM" add my-feature e2e-test -a test-agent --deps "backend,frontend" --desc "E2E 測試"

# 查看可派發任務
"$TM" ready my-feature

# 派發完成後，依賴任務自動解鎖
"$TM" update my-feature design done
"$TM" ready my-feature  # → backend + frontend 同時可派發
```

### Debate（多方辯論）

適用：架構決策、Code Review、技術選型。

```bash
# 建立辯論
"$TM" init arch-review --mode debate -g "微服務 vs 單體架構？"

# 加入辯論者
"$TM" add-debater arch-review security-expert -p "資安角度"
"$TM" add-debater arch-review perf-expert -p "效能角度"
"$TM" add-debater arch-review dx-expert -p "開發體驗角度"

# 開始辯論
"$TM" round arch-review start

# 提交各方觀點
"$TM" round arch-review submit -d security-expert -t "微服務隔離性更好..."
"$TM" round arch-review submit -d perf-expert -t "單體減少網路開銷..."

# 交叉審查 → 綜合結論
"$TM" round arch-review cross-review
"$TM" round arch-review synthesize
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

直接在 Claude Code 對話中執行 `"$TM"` 指令，根據結果決定下一步。

### 搭配 CLI Agent — Headless vs Interactive

兩種執行模式，根據任務性質選擇：

| 考量 | → Headless | → Interactive |
|------|-----------|---------------|
| 任務自成一體，單次完成 | Yes | — |
| 需要多輪對話、迭代修正 | — | Yes |
| 成本敏感 | Yes（token 較少） | — |
| 需要跨回合保留 context | — | Yes |
| 多個獨立子任務批次處理 | Yes | — |
| 複雜 debug / design exploration | — | Yes |

**Headless 模式**（單次呼叫，無狀態）：

```bash
# 取得待辦任務
task=$("$TM" ready my-feature --json | jq -r '.[0].id')
desc=$("$TM" ready my-feature --json | jq -r '.[0].description')

# 派發給 claude headless
"$TM" update my-feature "$task" in-progress
result=$(claude -p "$desc" --cwd /path/to/project --allowedTools "Read,Edit,Bash" --output-format json | jq -r '.result')
"$TM" result my-feature "$task" "$result"
"$TM" update my-feature "$task" done
```

**Interactive 模式**（tmux 多輪對話，保留 context）：

```bash
# 使用 claude-code-interactive / codex-cli-interactive / gemini-cli-interactive
# 透過 tmux send-keys 進行多輪交互

# 啟動 interactive session
tmux new-window -t default -n "task-$task"
tmux send-keys -t "default:task-$task" "claude" Enter

# 發送任務描述
sleep 3
tmux send-keys -t "default:task-$task" -l "$desc"
tmux send-keys -t "default:task-$task" Enter

# 後續追問、迭代修正...
tmux send-keys -t "default:task-$task" -l "請再加上錯誤處理"
tmux send-keys -t "default:task-$task" Enter

# 讀取結果
tmux capture-pane -t "default:task-$task" -p -S -200
```

**Memory 注意事項**: Interactive 模式累積 context，長時間運行可能耗盡 context window。
對於超長任務，建議分段：完成一個階段後總結要點，開新 session 繼續。

### 搭配 OpenClaw

透過 OpenClaw 發送任務到 Telegram 群組中的 Agent：

```bash
task=$("$TM" next my-api --json | jq -r '.id')
openclaw message send --channel telegram --target <group-id> \
  --message "請執行任務: $task"
```

## 工作流範例

### 典型 DAG 工作流

```
1. "$TM" init → 建立專案
2. "$TM" add  → 定義所有任務和依賴
3. "$TM" graph → 確認依賴結構
4. LOOP:
   a. "$TM" ready → 取得可派發任務
   b. 派發給 agent（手動/headless/interactive/openclaw）
   c. "$TM" update → 標記 in-progress
   d. 等待結果
   e. "$TM" result → 記錄結果
   f. "$TM" update → 標記 done
   g. 回到 4a 直到全部完成
5. "$TM" log → 查看完整紀錄
```

---

## Engine C — Hybrid 模式（Native + Custom）

當你需要 Agent Teams 的即時協作能力，又想保留持久化任務紀錄時，可以結合兩者：

```
1. 用 task_manager.py 規劃任務結構和依賴關係
2. 用 Agent Teams 實際執行（teammates 自行認領 ready 任務）
3. 執行結果寫回 task_manager.py 的 JSON 檔
```

### 範例：Hybrid 工作流

```bash
TM="~/.local/bin/python3 ~/.claude/skills/team-tasks/scripts/task_manager.py"

# Step 1: 用 Custom Pipeline 規劃任務結構
"$TM" init user-auth --mode dag -g "Build OAuth2 authentication system"
"$TM" add user-auth design -a planner --desc "Design OAuth2 flow and API spec"
"$TM" add user-auth backend -a code-agent --deps "design" --desc "Implement OAuth2 endpoints"
"$TM" add user-auth frontend -a ui-agent --deps "design" --desc "Build login UI"
"$TM" add user-auth test -a test-agent --deps "backend,frontend" --desc "E2E auth tests"
```

然後在 Claude Code 對話中：

```
我已經用 task_manager.py 建好了 user-auth 專案的任務結構。
請建立一個 Agent Team，每個 teammate 認領一個 ready 任務。
完成後把結果寫回 task_manager.py。

查看可派發任務：
~/.local/bin/python3 ~/.claude/skills/team-tasks/scripts/task_manager.py ready user-auth
```

### 何時用 Hybrid

- 大型專案需要跨多個 session 追蹤進度
- 部分任務適合 Agent Teams 即時協作，部分適合 headless 批次處理
- 需要持久化紀錄（JSON 檔）作為審計或回顧用途

---

## See Also

- **`maestro`** — For cross-CLI dispatch and cost-optimized routing (Claude/Codex/Gemini), use `maestro` instead of team-tasks.

## Additional Resources

### Reference Files

- **`references/advanced-patterns.md`** — 進階使用模式、Agent Teams 整合範例、混合 CLI 派發

### Example Files

- **`examples/linear-demo.sh`** — Linear 模式完整範例
- **`examples/dag-demo.sh`** — DAG 模式完整範例

## Continuous Improvement

This skill evolves with each use. After every invocation:

1. **Reflect** — Identify what worked, what caused friction, and any unexpected issues
2. **Record** — Append a concise lesson to `lessons.md` in this skill's directory
3. **Refine** — When a pattern recurs (2+ times), update SKILL.md directly

### lessons.md Entry Format

```
### YYYY-MM-DD — Brief title
- **Friction**: What went wrong or was suboptimal
- **Fix**: How it was resolved
- **Rule**: Generalizable takeaway for future invocations
```

Accumulated lessons signal when to run `/skill-optimizer` for a deeper structural review.
