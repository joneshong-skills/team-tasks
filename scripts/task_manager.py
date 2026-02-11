#!/usr/bin/env python3
"""team-tasks: Multi-agent pipeline coordination via JSON task files.

Modes:
  linear  – Sequential stages, auto-advancement on completion.
  dag     – Dependency graph, parallel dispatch when deps resolve.
  debate  – N agents examine same question, cross-review, synthesize.

Data dir: ~/.claude/data/team-tasks/ (override with TEAM_TASKS_DIR)
No external dependencies — Python 3.12+ stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Config ──────────────────────────────────────────────────────────────
DATA_DIR = Path(
    os.environ.get("TEAM_TASKS_DIR", os.path.expanduser("~/.claude/data/team-tasks"))
)
VALID_STATUSES = ("pending", "in-progress", "done", "failed", "skipped")
STATUS_ICONS = {
    "pending": "⏳",
    "in-progress": "🔄",
    "done": "✅",
    "failed": "❌",
    "skipped": "⏭️",
}

# ── Persistence helpers ─────────────────────────────────────────────────
def _project_path(name: str) -> Path:
    return DATA_DIR / f"{name}.json"


def load_project(name: str) -> dict:
    p = _project_path(name)
    if not p.exists():
        print(f"Error: project '{name}' not found at {p}", file=sys.stderr)
        sys.exit(1)
    with open(p) as f:
        return json.load(f)


def save_project(name: str, data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(_project_path(name), "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def list_projects() -> list[str]:
    if not DATA_DIR.exists():
        return []
    return sorted(p.stem for p in DATA_DIR.glob("*.json"))


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Data constructors ───────────────────────────────────────────────────
def make_stage(stage_id: str, *, desc: str = "", agent: str = "") -> dict:
    return {
        "id": stage_id,
        "agent": agent or stage_id,
        "description": desc,
        "status": "pending",
        "result": "",
        "assigned_at": "",
        "completed_at": "",
    }


def make_task(task_id: str, *, agent: str = "", desc: str = "", deps: list[str] | None = None) -> dict:
    return {
        "id": task_id,
        "agent": agent or task_id,
        "description": desc,
        "dependencies": deps or [],
        "status": "pending",
        "result": "",
        "assigned_at": "",
        "completed_at": "",
    }


# ── DAG helpers ─────────────────────────────────────────────────────────
def compute_ready_tasks(proj: dict) -> list[dict]:
    tasks = proj.get("tasks", [])
    done_ids = {t["id"] for t in tasks if t["status"] == "done"}
    ready = []
    for t in tasks:
        if t["status"] != "pending":
            continue
        if all(d in done_ids for d in t.get("dependencies", [])):
            ready.append(t)
    return ready


def detect_cycles(proj: dict) -> list[str]:
    tasks = {t["id"]: t.get("dependencies", []) for t in proj.get("tasks", [])}
    visited: set[str] = set()
    stack: set[str] = set()
    cycles: list[str] = []

    def dfs(node: str) -> bool:
        visited.add(node)
        stack.add(node)
        for dep in tasks.get(node, []):
            if dep not in visited:
                if dfs(dep):
                    return True
            elif dep in stack:
                cycles.append(f"{node} -> {dep}")
                return True
        stack.discard(node)
        return False

    for tid in tasks:
        if tid not in visited:
            dfs(tid)
    return cycles


# ── Commands ────────────────────────────────────────────────────────────
def cmd_init(args: argparse.Namespace) -> None:
    """Create a new project."""
    name = args.project
    if _project_path(name).exists() and not args.force:
        print(f"Error: project '{name}' already exists. Use --force to overwrite.", file=sys.stderr)
        sys.exit(1)

    mode = args.mode
    proj: dict = {
        "name": name,
        "mode": mode,
        "goal": args.goal or "",
        "created_at": _now(),
        "workspace": args.workspace or "",
    }

    if mode == "linear":
        stages = [s.strip() for s in (args.pipeline or "").split(",") if s.strip()]
        if not stages:
            print("Error: linear mode requires --pipeline 'a,b,c'", file=sys.stderr)
            sys.exit(1)
        proj["stages"] = [make_stage(s) for s in stages]
        proj["current_stage"] = 0
    elif mode == "dag":
        proj["tasks"] = []
    elif mode == "debate":
        proj["debaters"] = []
        proj["rounds"] = []
        proj["question"] = args.goal or ""
    else:
        print(f"Error: unknown mode '{mode}'", file=sys.stderr)
        sys.exit(1)

    save_project(name, proj)
    print(f"✅ 專案 '{name}' 已建立 (模式: {mode})")


def cmd_add(args: argparse.Namespace) -> None:
    """Add a task (DAG mode)."""
    proj = load_project(args.project)
    if proj["mode"] != "dag":
        print("Error: 'add' is for DAG mode only. Use 'init' with --mode dag.", file=sys.stderr)
        sys.exit(1)

    deps = [d.strip() for d in (args.deps or "").split(",") if d.strip()]
    task = make_task(args.task_id, agent=args.agent or "", desc=args.desc or "", deps=deps)
    proj.setdefault("tasks", []).append(task)

    cycles = detect_cycles(proj)
    if cycles:
        print(f"Error: cycle detected: {cycles}", file=sys.stderr)
        sys.exit(1)

    save_project(args.project, proj)
    dep_str = f" (deps: {', '.join(deps)})" if deps else ""
    print(f"✅ 任務 '{args.task_id}' 已新增{dep_str}")


def cmd_add_debater(args: argparse.Namespace) -> None:
    """Register a debate participant."""
    proj = load_project(args.project)
    if proj["mode"] != "debate":
        print("Error: 'add-debater' is for debate mode only.", file=sys.stderr)
        sys.exit(1)

    debater = {
        "id": args.debater_id,
        "agent": args.agent or args.debater_id,
        "perspective": args.perspective or "",
        "added_at": _now(),
    }
    proj.setdefault("debaters", []).append(debater)
    save_project(args.project, proj)
    label = f" ({args.perspective})" if args.perspective else ""
    print(f"✅ 辯論者 '{args.debater_id}'{label} 已加入")


def cmd_status(args: argparse.Namespace) -> None:
    """Display project status."""
    proj = load_project(args.project)

    if args.json:
        print(json.dumps(proj, indent=2, ensure_ascii=False))
        return

    mode = proj["mode"]
    print(f"\n📋 專案: {proj['name']}  模式: {mode}")
    if proj.get("goal"):
        print(f"🎯 目標: {proj['goal']}")
    if proj.get("workspace"):
        print(f"📁 工作區: {proj['workspace']}")
    print()

    if mode == "linear":
        current = proj.get("current_stage", 0)
        for i, stage in enumerate(proj.get("stages", [])):
            icon = STATUS_ICONS.get(stage["status"], "?")
            marker = " 👈" if i == current and stage["status"] != "done" else ""
            print(f"  {icon} [{i}] {stage['id']} — {stage['status']}{marker}")
            if stage.get("description"):
                print(f"       {stage['description']}")
    elif mode == "dag":
        tasks = proj.get("tasks", [])
        ready = {t["id"] for t in compute_ready_tasks(proj)}
        for t in tasks:
            icon = STATUS_ICONS.get(t["status"], "?")
            deps = f" (deps: {', '.join(t['dependencies'])})" if t.get("dependencies") else ""
            rdy = " 🟢 可派發" if t["id"] in ready else ""
            print(f"  {icon} {t['id']}{deps}{rdy}")
            if t.get("description"):
                print(f"       {t['description']}")
    elif mode == "debate":
        debaters = proj.get("debaters", [])
        rounds = proj.get("rounds", [])
        print(f"  辯論者 ({len(debaters)}):")
        for d in debaters:
            persp = f" — {d['perspective']}" if d.get("perspective") else ""
            print(f"    👤 {d['id']}{persp}")
        print(f"\n  輪次 ({len(rounds)}):")
        for i, r in enumerate(rounds):
            phase = r.get("phase", "?")
            resp_count = len(r.get("responses", []))
            print(f"    📝 第 {i+1} 輪: {phase} ({resp_count} 份回應)")
    print()


def cmd_next(args: argparse.Namespace) -> None:
    """Get the next pending stage (linear mode)."""
    proj = load_project(args.project)
    if proj["mode"] != "linear":
        print("Error: 'next' is for linear mode. Use 'ready' for DAG.", file=sys.stderr)
        sys.exit(1)

    stages = proj.get("stages", [])
    current = proj.get("current_stage", 0)
    if current >= len(stages):
        print("🎉 所有階段已完成！")
        return

    stage = stages[current]
    if args.json:
        print(json.dumps(stage, indent=2, ensure_ascii=False))
    else:
        print(f"⏭️ 下一階段: {stage['id']} (agent: {stage['agent']})")
        if stage.get("description"):
            print(f"   描述: {stage['description']}")


def cmd_ready(args: argparse.Namespace) -> None:
    """List tasks ready for dispatch (DAG mode)."""
    proj = load_project(args.project)
    if proj["mode"] != "dag":
        print("Error: 'ready' is for DAG mode. Use 'next' for linear.", file=sys.stderr)
        sys.exit(1)

    ready = compute_ready_tasks(proj)
    if not ready:
        done_count = sum(1 for t in proj.get("tasks", []) if t["status"] == "done")
        total = len(proj.get("tasks", []))
        if done_count == total and total > 0:
            print("🎉 所有任務已完成！")
        else:
            print("⏳ 目前無可派發任務（等待依賴完成）")
        return

    if args.json:
        print(json.dumps(ready, indent=2, ensure_ascii=False))
    else:
        print(f"🟢 可派發任務 ({len(ready)}):\n")
        for t in ready:
            print(f"  • {t['id']} (agent: {t['agent']})")
            if t.get("description"):
                print(f"    {t['description']}")


def cmd_update(args: argparse.Namespace) -> None:
    """Update a task/stage status."""
    proj = load_project(args.project)
    mode = proj["mode"]
    status = args.status
    target_id = args.task_id

    if status not in VALID_STATUSES:
        print(f"Error: invalid status '{status}'. Valid: {', '.join(VALID_STATUSES)}", file=sys.stderr)
        sys.exit(1)

    if mode == "linear":
        stages = proj.get("stages", [])
        found = False
        for i, s in enumerate(stages):
            if s["id"] == target_id:
                s["status"] = status
                if status == "in-progress":
                    s["assigned_at"] = _now()
                elif status in ("done", "failed", "skipped"):
                    s["completed_at"] = _now()
                    # Auto-advance
                    if status == "done" and i == proj.get("current_stage", 0):
                        proj["current_stage"] = i + 1
                        if i + 1 < len(stages):
                            print(f"⏭️ 自動推進至: {stages[i+1]['id']}")
                found = True
                break
        if not found:
            print(f"Error: stage '{target_id}' not found", file=sys.stderr)
            sys.exit(1)
    elif mode == "dag":
        tasks = proj.get("tasks", [])
        found = False
        for t in tasks:
            if t["id"] == target_id:
                t["status"] = status
                if status == "in-progress":
                    t["assigned_at"] = _now()
                elif status in ("done", "failed", "skipped"):
                    t["completed_at"] = _now()
                found = True
                break
        if not found:
            print(f"Error: task '{target_id}' not found", file=sys.stderr)
            sys.exit(1)

        # Show newly unblocked tasks
        if status == "done":
            newly_ready = compute_ready_tasks(proj)
            if newly_ready:
                names = ", ".join(t["id"] for t in newly_ready)
                print(f"🔓 新解鎖任務: {names}")
    else:
        print(f"Error: update not supported in '{mode}' mode", file=sys.stderr)
        sys.exit(1)

    save_project(args.project, proj)
    print(f"{STATUS_ICONS.get(status, '?')} '{target_id}' → {status}")


def cmd_result(args: argparse.Namespace) -> None:
    """Record task output/result."""
    proj = load_project(args.project)
    mode = proj["mode"]
    target_id = args.task_id
    result_text = args.text

    items = proj.get("stages" if mode == "linear" else "tasks", [])
    found = False
    for item in items:
        if item["id"] == target_id:
            item["result"] = result_text
            if item["status"] == "pending":
                item["status"] = "in-progress"
                item["assigned_at"] = _now()
            found = True
            break

    if not found:
        print(f"Error: '{target_id}' not found", file=sys.stderr)
        sys.exit(1)

    save_project(args.project, proj)
    print(f"📝 '{target_id}' 結果已記錄 ({len(result_text)} chars)")


def cmd_round(args: argparse.Namespace) -> None:
    """Manage debate rounds."""
    proj = load_project(args.project)
    if proj["mode"] != "debate":
        print("Error: 'round' is for debate mode only.", file=sys.stderr)
        sys.exit(1)

    action = args.action
    rounds = proj.setdefault("rounds", [])
    debaters = proj.get("debaters", [])

    if action == "start":
        new_round = {
            "round_number": len(rounds) + 1,
            "phase": "initial",
            "started_at": _now(),
            "responses": [],
        }
        rounds.append(new_round)
        save_project(args.project, proj)
        print(f"📢 第 {new_round['round_number']} 輪辯論開始")
        print(f"   問題: {proj.get('question', proj.get('goal', ''))}")
        print(f"   請收集 {len(debaters)} 位辯論者的回應")

    elif action == "submit":
        if not rounds:
            print("Error: no active round. Use 'round start' first.", file=sys.stderr)
            sys.exit(1)
        current_round = rounds[-1]
        response = {
            "debater_id": args.debater_id,
            "content": args.text or "",
            "submitted_at": _now(),
            "phase": current_round["phase"],
        }
        current_round.setdefault("responses", []).append(response)
        save_project(args.project, proj)
        print(f"📝 '{args.debater_id}' 回應已提交 (第 {current_round['round_number']} 輪 - {current_round['phase']})")

    elif action == "cross-review":
        if not rounds:
            print("Error: no round data.", file=sys.stderr)
            sys.exit(1)
        current_round = rounds[-1]
        current_round["phase"] = "cross-review"
        save_project(args.project, proj)

        # Generate cross-review prompts
        responses = [r for r in current_round.get("responses", []) if r["phase"] == "initial"]
        print(f"\n🔄 交叉審查 — 共 {len(responses)} 份初始回應\n")
        for debater in debaters:
            others = [r for r in responses if r["debater_id"] != debater["id"]]
            if others:
                print(f"📋 給 {debater['id']} 的審查提示:")
                print(f"   請審查以下觀點並提出回饋:\n")
                for r in others:
                    preview = r["content"][:200] + "..." if len(r["content"]) > 200 else r["content"]
                    print(f"   [{r['debater_id']}]: {preview}\n")

    elif action == "synthesize":
        if not rounds:
            print("Error: no round data.", file=sys.stderr)
            sys.exit(1)
        current_round = rounds[-1]
        current_round["phase"] = "synthesis"
        save_project(args.project, proj)

        all_responses = current_round.get("responses", [])
        initial = [r for r in all_responses if r["phase"] == "initial"]
        reviews = [r for r in all_responses if r["phase"] == "cross-review"]
        print(f"\n🧠 綜合階段")
        print(f"   初始回應: {len(initial)} 份")
        print(f"   交叉審查: {len(reviews)} 份")
        print(f"\n   請基於所有回應產出最終綜合結論。")

    elif action == "status":
        if not rounds:
            print("尚無辯論輪次")
            return
        current_round = rounds[-1]
        responses = current_round.get("responses", [])
        print(f"\n📊 第 {current_round['round_number']} 輪 — 階段: {current_round['phase']}")
        responded = {r["debater_id"] for r in responses if r["phase"] == current_round["phase"]}
        for d in debaters:
            icon = "✅" if d["id"] in responded else "⏳"
            print(f"   {icon} {d['id']}")

    else:
        print(f"Error: unknown round action '{action}'", file=sys.stderr)
        sys.exit(1)


def cmd_graph(args: argparse.Namespace) -> None:
    """Visualize DAG dependencies (ASCII)."""
    proj = load_project(args.project)
    if proj["mode"] == "linear":
        stages = proj.get("stages", [])
        for i, s in enumerate(stages):
            icon = STATUS_ICONS.get(s["status"], "?")
            arrow = " → " if i < len(stages) - 1 else ""
            print(f"  {icon} {s['id']}{arrow}", end="")
        print()
    elif proj["mode"] == "dag":
        tasks = proj.get("tasks", [])
        if not tasks:
            print("(空)")
            return
        for t in tasks:
            icon = STATUS_ICONS.get(t["status"], "?")
            deps = t.get("dependencies", [])
            if deps:
                for d in deps:
                    print(f"  {d} ──→ {icon} {t['id']}")
            else:
                print(f"  (root) ──→ {icon} {t['id']}")
    elif proj["mode"] == "debate":
        debaters = proj.get("debaters", [])
        print("  ┌─ 問題 ─┐")
        for d in debaters:
            print(f"  │  👤 {d['id']}")
        print("  └─ 綜合 ─┘")


def cmd_reset(args: argparse.Namespace) -> None:
    """Reset all tasks to pending."""
    proj = load_project(args.project)
    mode = proj["mode"]

    if mode == "linear":
        for s in proj.get("stages", []):
            s["status"] = "pending"
            s["result"] = ""
            s["assigned_at"] = ""
            s["completed_at"] = ""
        proj["current_stage"] = 0
    elif mode == "dag":
        for t in proj.get("tasks", []):
            t["status"] = "pending"
            t["result"] = ""
            t["assigned_at"] = ""
            t["completed_at"] = ""
    elif mode == "debate":
        proj["rounds"] = []

    save_project(args.project, proj)
    print(f"🔄 專案 '{args.project}' 已重置")


def cmd_list(args: argparse.Namespace) -> None:
    """List all projects."""
    projects = list_projects()
    if not projects:
        print("尚無專案。使用 'init' 建立。")
        return

    if args.json:
        result = []
        for name in projects:
            proj = load_project(name)
            result.append({"name": name, "mode": proj["mode"], "goal": proj.get("goal", "")})
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"\n📂 專案列表 ({len(projects)}):\n")
        for name in projects:
            proj = load_project(name)
            mode = proj["mode"]
            goal = proj.get("goal", "")[:60]
            print(f"  • {name} [{mode}] {goal}")
        print()


def cmd_log(args: argparse.Namespace) -> None:
    """Show task results/history."""
    proj = load_project(args.project)
    mode = proj["mode"]

    items = proj.get("stages" if mode == "linear" else "tasks", [])
    print(f"\n📜 '{args.project}' 執行紀錄:\n")
    for item in items:
        if item.get("result") or item["status"] != "pending":
            icon = STATUS_ICONS.get(item["status"], "?")
            print(f"  {icon} {item['id']} [{item['status']}]")
            if item.get("assigned_at"):
                print(f"     開始: {item['assigned_at']}")
            if item.get("completed_at"):
                print(f"     完成: {item['completed_at']}")
            if item.get("result"):
                preview = item["result"][:300]
                print(f"     結果: {preview}")
            print()


# ── CLI ─────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(
        prog="task_manager",
        description="team-tasks: 多 Agent 任務協調工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            模式:
              linear   依序執行 pipeline（如 code → test → docs）
              dag      依賴圖，依賴解除時可平行派發
              debate   多 Agent 辯論 → 交叉審查 → 綜合結論
        """),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p = sub.add_parser("init", help="建立新專案")
    p.add_argument("project", help="專案名稱")
    p.add_argument("--mode", "-m", choices=["linear", "dag", "debate"], default="dag")
    p.add_argument("--goal", "-g", help="專案目標或辯論問題")
    p.add_argument("--pipeline", "-p", help="Linear 模式的 pipeline（逗號分隔）")
    p.add_argument("--workspace", "-w", help="工作目錄路徑")
    p.add_argument("--force", action="store_true", help="覆蓋已存在的專案")

    # add (DAG)
    p = sub.add_parser("add", help="新增任務 (DAG)")
    p.add_argument("project")
    p.add_argument("task_id", help="任務 ID")
    p.add_argument("--agent", "-a", help="負責的 agent")
    p.add_argument("--desc", "-d", help="任務描述")
    p.add_argument("--deps", help="依賴任務（逗號分隔）")

    # add-debater (debate)
    p = sub.add_parser("add-debater", help="新增辯論者 (debate)")
    p.add_argument("project")
    p.add_argument("debater_id", help="辯論者 ID")
    p.add_argument("--agent", "-a", help="Agent 名稱")
    p.add_argument("--perspective", "-p", help="觀點角度")

    # status
    p = sub.add_parser("status", help="顯示專案狀態")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")

    # next (linear)
    p = sub.add_parser("next", help="取得下一階段 (linear)")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")

    # ready (DAG)
    p = sub.add_parser("ready", help="列出可派發任務 (DAG)")
    p.add_argument("project")
    p.add_argument("--json", action="store_true")

    # update
    p = sub.add_parser("update", help="更新任務狀態")
    p.add_argument("project")
    p.add_argument("task_id", help="任務/階段 ID")
    p.add_argument("status", choices=VALID_STATUSES)

    # result
    p = sub.add_parser("result", help="記錄任務結果")
    p.add_argument("project")
    p.add_argument("task_id")
    p.add_argument("text", help="結果文字")

    # round (debate)
    p = sub.add_parser("round", help="管理辯論輪次")
    p.add_argument("project")
    p.add_argument("action", choices=["start", "submit", "cross-review", "synthesize", "status"])
    p.add_argument("--debater-id", "-d", help="辯論者 ID (submit)")
    p.add_argument("--text", "-t", help="回應內容 (submit)")

    # graph
    p = sub.add_parser("graph", help="視覺化依賴關係")
    p.add_argument("project")

    # log
    p = sub.add_parser("log", help="顯示執行紀錄")
    p.add_argument("project")

    # reset
    p = sub.add_parser("reset", help="重置專案狀態")
    p.add_argument("project")

    # list
    p = sub.add_parser("list", help="列出所有專案")
    p.add_argument("--json", action="store_true")

    args = parser.parse_args()
    cmd_map = {
        "init": cmd_init,
        "add": cmd_add,
        "add-debater": cmd_add_debater,
        "status": cmd_status,
        "next": cmd_next,
        "ready": cmd_ready,
        "update": cmd_update,
        "result": cmd_result,
        "round": cmd_round,
        "graph": cmd_graph,
        "log": cmd_log,
        "reset": cmd_reset,
        "list": cmd_list,
    }
    cmd_map[args.command](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
