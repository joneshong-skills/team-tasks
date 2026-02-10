#!/usr/bin/env bash
# Linear 模式完整範例
# 模擬：Bug 修復 Pipeline（分析 → 修復 → 測試）
set -euo pipefail

TM="python3 $HOME/.claude/skills/team-tasks/scripts/task_manager.py"
PROJECT="bugfix-demo"

echo "=== Linear Pipeline Demo ==="
echo ""

# 1. 建立 linear 專案
echo "--- Step 1: Init project ---"
$TM init "$PROJECT" --mode linear \
    -g "Fix login timeout bug #42" \
    -p "analyst,developer,tester"
echo ""

# 2. 查看狀態
echo "--- Step 2: Status ---"
$TM status "$PROJECT"
echo ""

# 3. 第一階段：分析
echo "--- Step 3: Analyst phase ---"
$TM next "$PROJECT"
$TM update "$PROJECT" analyst in-progress
echo "  [analyst working...]"
$TM result "$PROJECT" analyst "Root cause: session TTL set to 5s instead of 300s in config.yaml line 42"
$TM update "$PROJECT" analyst done
echo ""

# 4. 第二階段：修復
echo "--- Step 4: Developer phase ---"
$TM next "$PROJECT"
$TM update "$PROJECT" developer in-progress
echo "  [developer working...]"
$TM result "$PROJECT" developer "Fixed config.yaml: session_ttl changed from 5 to 300. Also added validation."
$TM update "$PROJECT" developer done
echo ""

# 5. 第三階段：測試
echo "--- Step 5: Tester phase ---"
$TM next "$PROJECT"
$TM update "$PROJECT" tester in-progress
echo "  [tester working...]"
$TM result "$PROJECT" tester "All 12 login tests pass. Session persists correctly for 5 minutes."
$TM update "$PROJECT" tester done
echo ""

# 6. 最終狀態
echo "--- Step 6: Final status ---"
$TM status "$PROJECT"
echo ""

# 7. 查看紀錄
echo "--- Step 7: Execution log ---"
$TM log "$PROJECT"
echo ""

# 8. 視覺化
echo "--- Step 8: Graph ---"
$TM graph "$PROJECT"
echo ""

echo "=== Demo Complete ==="
