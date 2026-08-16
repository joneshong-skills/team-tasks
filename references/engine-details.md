# Engine Details

## Engine A — Native Agent Teams

### 前置條件

**settings.json**（推薦）：
```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

**Shell**：`export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`

確認：
```bash
cat ~/.claude/settings.json | ~/.local/bin/python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('env',{}).get('CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS','未設定'))"
```

### 快速開始

```
建立一個 agent team 來開發使用者系統：
- 一個 teammate 負責後端 API
- 一個 teammate 負責前端 React 元件
- 一個 teammate 負責寫測試
```

或指定模型/數量：
```
Create a team with 3 teammates using Sonnet.
Teammate 1: API design. Teammate 2: implementation. Teammate 3: code review.
```

### 架構

| 元件 | 角色 |
|------|------|
| **Team Lead** | 主 session，產生 teammates、協調工作 |
| **Teammates** | 獨立 Claude Code 實例，各自處理分配的任務 |
| **Task List** | 共享任務清單，支援依賴追蹤，teammates 可自行認領 |
| **Mailbox** | agents 之間的直接通訊系統 |

解鎖工具：`TaskCreate`、`TaskUpdate`、`TaskList`、`TaskGet`、`SendMessage`（`TeamCreate` 已不存在，2026-08-16 於 CC 2.1.233 實測——單一隱含團隊，細節見 SKILL.md）

### 顯示模式

| 模式 | 設定 | 說明 |
|------|------|------|
| **In-process** | `"teammateMode": "in-process"` | 同一終端，Shift+Up/Down 切換 |
| **Split panes** | `"teammateMode": "split"` | 每個 teammate 獨立 tmux/iTerm2 面板 |

CLI 啟動：`claude --teammate-mode in-process`

### 關鍵功能

- **Plan Approval** — 要求 teammates 先寫計畫，Lead 核准後才改 code
- **Delegate Mode** — Shift+Tab 讓 Lead 只協調不寫 code
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

## Engine B — Custom Pipeline 完整指令範例

### Linear 模式

```bash
~/.local/bin/maestro project create my-api --mode linear \
  --goal "建立 REST API 並測試" \
  --pipeline "code-agent,test-agent,docs-agent"

~/.local/bin/maestro project next my-api
~/.local/bin/maestro project update my-api code-agent done
~/.local/bin/maestro project result my-api code-agent "API 實作完成，含 CRUD endpoints"
```

### DAG 模式

```bash
~/.local/bin/maestro project create my-feature --mode dag --goal "建立使用者系統"
~/.local/bin/maestro project add-task my-feature design --agent planner --desc "設計 API 規格"
~/.local/bin/maestro project add-task my-feature backend --agent code-agent --deps "design" --desc "實作後端"
~/.local/bin/maestro project add-task my-feature frontend --agent ui-agent --deps "design" --desc "實作前端"
~/.local/bin/maestro project add-task my-feature e2e-test --agent test-agent --deps "backend,frontend" --desc "E2E 測試"

~/.local/bin/maestro project ready my-feature
~/.local/bin/maestro project update my-feature design done
~/.local/bin/maestro project ready my-feature  # → backend + frontend 同時可派發
```

### Debate 模式

```bash
~/.local/bin/maestro project create arch-review --mode debate --goal "微服務 vs 單體架構？"
~/.local/bin/maestro project add-debater arch-review security-expert --perspective "資安角度"
~/.local/bin/maestro project add-debater arch-review perf-expert --perspective "效能角度"
~/.local/bin/maestro project add-debater arch-review dx-expert --perspective "開發體驗角度"

~/.local/bin/maestro project round arch-review start
~/.local/bin/maestro project round arch-review submit --debater security-expert --text "微服務隔離性更好..."
~/.local/bin/maestro project round arch-review submit --debater perf-expert --text "單體減少網路開銷..."
~/.local/bin/maestro project round arch-review cross-review
~/.local/bin/maestro project round arch-review synthesize
```

### Headless 派發

```bash
task=$(~/.local/bin/maestro project ready my-feature --json | jq -r '.[0].id')
desc=$(~/.local/bin/maestro project ready my-feature --json | jq -r '.[0].description')

~/.local/bin/maestro project update my-feature "$task" in-progress
result=$(claude -p "$desc" --cwd /path/to/project --allowedTools "Read,Edit,Bash" --output-format json | jq -r '.result')
~/.local/bin/maestro project result my-feature "$task" "$result"
~/.local/bin/maestro project update my-feature "$task" done
```

### tmux-relay 派發

```bash
POOL=~/.claude/skills/tmux-relay/scripts/pane_pool.py
RELAY=~/.claude/skills/tmux-relay/scripts/relay.py
bash $POOL acquire 2

bash $RELAY "$PANE_A" "" "分析後端 $task_a" --no-forward --signal /tmp/relay-a.done
bash $RELAY "$PANE_B" "" "分析前端 $task_b" --no-forward --signal /tmp/relay-b.done
# 讀取 signal file 的 result_file，合併後派發給下一個 pane
```

---

## Engine C — Hybrid 模式（Native + Custom）

```bash
# Step 1: maestro project 規劃任務結構
~/.local/bin/maestro project create user-auth --mode dag --goal "Build OAuth2 authentication system"
~/.local/bin/maestro project add-task user-auth design --agent planner --desc "Design OAuth2 flow and API spec"
~/.local/bin/maestro project add-task user-auth backend --agent code-agent --deps "design" --desc "Implement OAuth2 endpoints"
~/.local/bin/maestro project add-task user-auth frontend --agent ui-agent --deps "design" --desc "Build login UI"
~/.local/bin/maestro project add-task user-auth test --agent test-agent --deps "backend,frontend" --desc "E2E auth tests"
```

然後在 Claude Code 對話中：
```
我已經用 maestro project 建好了 user-auth 專案的任務結構。
請建立一個 Agent Team，每個 teammate 認領一個 ready 任務。
完成後用 maestro project result 寫回結果。

查看可派發任務：maestro project ready user-auth
```

**何時用 Hybrid**：大型專案需跨 session 追蹤 + 部分任務適合 Agent Teams + 需持久化紀錄作審計。

---

## 典型 DAG 工作流

```
1. maestro project create → 建立專案
2. maestro project add-task → 定義所有任務和依賴
3. maestro project status → 確認依賴結構
4. LOOP:
   a. maestro project ready → 取得可派發任務
   b. 派發給 agent（手動/headless/interactive/openclaw）
   c. maestro project update → 標記 in-progress
   d. 等待結果
   e. maestro project result → 記錄結果
   f. maestro project update → 標記 done
   g. 回到 4a 直到全部完成
5. maestro project status → 查看完整紀錄
```
