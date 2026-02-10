[English](README.md) | [繁體中文](README.zh.md)

# team-tasks

Multi-agent task coordination for Claude Code. Orchestrate development workflows using JSON task files with three modes: linear pipelines, DAG-based parallel execution, and multi-party debate.

## What It Does

`team-tasks` provides a Python CLI (`task_manager.py`) that lets you:

- **Linear Pipeline** — Run tasks in strict sequence (e.g., code -> test -> docs). Ideal for bug fixes and step-by-step verification.
- **DAG (Directed Acyclic Graph)** — Define tasks with dependencies and run independent tasks in parallel. Suited for large features with multiple modules.
- **Debate** — Coordinate multiple perspectives on a decision (e.g., architecture review), with rounds of argument, cross-review, and synthesis.

Tasks are stored as JSON in `~/.claude/data/team-tasks/` (configurable via `TEAM_TASKS_DIR`).

## Installation

This is a [Claude Code skill](https://docs.anthropic.com/en/docs/claude-code). To install it, add the skill to your Claude Code configuration:

```bash
# Clone into your skills directory
git clone https://github.com/joneshong-skills/team-tasks.git ~/.claude/skills/team-tasks
```

The skill is automatically activated when you ask Claude Code to coordinate agents, manage team tasks, create pipelines, dispatch work, run parallel tasks, start debates, or discuss task orchestration.

## Usage

Set up the CLI alias:

```bash
TM="python3 ~/.claude/skills/team-tasks/scripts/task_manager.py"
```

### Linear Mode

```bash
$TM init my-api --mode linear \
  -g "Build REST API and test" \
  -p "code-agent,test-agent,docs-agent"

$TM next my-api
$TM update my-api code-agent done
$TM result my-api code-agent "API implemented with CRUD endpoints"
```

### DAG Mode

```bash
$TM init my-feature --mode dag -g "Build user system"
$TM add my-feature design -a planner --desc "Design API spec"
$TM add my-feature backend -a code-agent --deps "design" --desc "Implement backend"
$TM add my-feature frontend -a ui-agent --deps "design" --desc "Implement frontend"
$TM add my-feature e2e-test -a test-agent --deps "backend,frontend" --desc "E2E tests"

$TM ready my-feature   # shows tasks with all dependencies met
```

### Debate Mode

```bash
$TM init arch-review --mode debate -g "Microservices vs monolith?"
$TM add-debater arch-review security-expert -p "Security perspective"
$TM add-debater arch-review perf-expert -p "Performance perspective"

$TM round arch-review start
$TM round arch-review submit -d security-expert -t "Microservices offer better isolation..."
$TM round arch-review cross-review
$TM round arch-review synthesize
```

### Dispatching to Headless Agents

```bash
task=$($TM ready my-feature --json | jq -r '.[0].id')
desc=$($TM ready my-feature --json | jq -r '.[0].description')

$TM update my-feature "$task" in-progress
result=$(claude -p "$desc" --allowedTools "Read,Edit,Bash" --output-format json | jq -r '.result')
$TM result my-feature "$task" "$result"
$TM update my-feature "$task" done
```

## Command Reference

| Command | Mode | Description |
|---------|------|-------------|
| `init <project>` | All | Create project (`--mode linear\|dag\|debate`) |
| `add <project> <task>` | DAG | Add task (`--deps`, `--agent`, `--desc`) |
| `add-debater <project> <id>` | Debate | Add debater (`--perspective`) |
| `status <project>` | All | Show project status |
| `next <project>` | Linear | Get next stage |
| `ready <project>` | DAG | List dispatchable tasks |
| `update <project> <task> <status>` | Linear/DAG | Update status |
| `result <project> <task> <text>` | Linear/DAG | Record result |
| `round <project> <action>` | Debate | Manage debate rounds |
| `graph <project>` | All | Visualize dependencies |
| `log <project>` | Linear/DAG | Show execution log |
| `reset <project>` | All | Reset all state |
| `list` | -- | List all projects |

## License

MIT
