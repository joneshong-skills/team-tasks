[English](README.md) | [繁體中文](README.zh.md)

# team-tasks

Claude Code 的多代理任務協調。使用 JSON 任務檔案編排開發工作流程，支援三種模式：線性管線、DAG 並行執行和多方辯論。

## 功能特色

`team-tasks` 提供 Python CLI（`task_manager.py`），讓您可以：

- **線性管線** — 按嚴格順序執行任務（例如 程式碼 -> 測試 -> 文件）。適合修復 bug 和逐步驗證。
- **DAG（有向無環圖）** — 定義帶有依賴關係的任務，並行執行獨立任務。適合具有多個模組的大型功能。
- **辯論** — 協調對決策的多方觀點（例如架構審查），包含論述、交叉審查和綜合等回合。

任務以 JSON 格式儲存在 `~/.claude/data/team-tasks/`（可透過 `TEAM_TASKS_DIR` 設定）。

## 安裝

這是一個 [Claude Code 技能](https://docs.anthropic.com/en/docs/claude-code)。安裝方式：

```bash
# Clone 到技能目錄
git clone https://github.com/joneshong-skills/team-tasks.git ~/.claude/skills/team-tasks
```

當您要求 Claude Code 協調代理、管理團隊任務、建立管線、分派工作、執行並行任務、開始辯論或討論任務編排時，技能會自動啟動。

## 使用方式

設定 CLI 別名：

```bash
TM="python3 ~/.claude/skills/team-tasks/scripts/task_manager.py"
```

### 線性模式

```bash
$TM init my-api --mode linear \
  -g "Build REST API and test" \
  -p "code-agent,test-agent,docs-agent"

$TM next my-api
$TM update my-api code-agent done
$TM result my-api code-agent "API implemented with CRUD endpoints"
```

### DAG 模式

```bash
$TM init my-feature --mode dag -g "Build user system"
$TM add my-feature design -a planner --desc "Design API spec"
$TM add my-feature backend -a code-agent --deps "design" --desc "Implement backend"
$TM add my-feature frontend -a ui-agent --deps "design" --desc "Implement frontend"
$TM add my-feature e2e-test -a test-agent --deps "backend,frontend" --desc "E2E tests"

$TM ready my-feature   # 顯示所有依賴都已滿足的任務
```

### 辯論模式

```bash
$TM init arch-review --mode debate -g "Microservices vs monolith?"
$TM add-debater arch-review security-expert -p "Security perspective"
$TM add-debater arch-review perf-expert -p "Performance perspective"

$TM round arch-review start
$TM round arch-review submit -d security-expert -t "Microservices offer better isolation..."
$TM round arch-review cross-review
$TM round arch-review synthesize
```

### 分派到 Headless 代理

```bash
task=$($TM ready my-feature --json | jq -r '.[0].id')
desc=$($TM ready my-feature --json | jq -r '.[0].description')

$TM update my-feature "$task" in-progress
result=$(claude -p "$desc" --allowedTools "Read,Edit,Bash" --output-format json | jq -r '.result')
$TM result my-feature "$task" "$result"
$TM update my-feature "$task" done
```

## 命令參考

| 命令 | 模式 | 說明 |
|------|------|------|
| `init <project>` | 全部 | 建立專案（`--mode linear\|dag\|debate`） |
| `add <project> <task>` | DAG | 新增任務（`--deps`、`--agent`、`--desc`） |
| `add-debater <project> <id>` | 辯論 | 新增辯論者（`--perspective`） |
| `status <project>` | 全部 | 顯示專案狀態 |
| `next <project>` | 線性 | 取得下一階段 |
| `ready <project>` | DAG | 列出可分派的任務 |
| `update <project> <task> <status>` | 線性/DAG | 更新狀態 |
| `result <project> <task> <text>` | 線性/DAG | 記錄結果 |
| `round <project> <action>` | 辯論 | 管理辯論回合 |
| `graph <project>` | 全部 | 視覺化依賴關係 |
| `log <project>` | 線性/DAG | 顯示執行日誌 |
| `reset <project>` | 全部 | 重置所有狀態 |
| `list` | -- | 列出所有專案 |

## 授權

MIT
