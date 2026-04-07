#!/usr/bin/env bash
# DAG 模式完整範例
# 模擬：使用者系統開發（設計 → 前端/後端並行 → 整合測試）
set -euo pipefail

PROJECT="user-system-demo"

echo "=== DAG Parallel Demo ==="
echo ""

# 1. 建立 DAG 專案
echo "--- Step 1: Init project ---"
maestro project create "$PROJECT" --mode dag -g "Build user registration and profile system"
echo ""

# 2. 新增任務（含依賴關係）
echo "--- Step 2: Add tasks with dependencies ---"
maestro project add-task "$PROJECT" design -a planner --desc "Design API spec and data models"
maestro project add-task "$PROJECT" backend -a code-agent --deps "design" --desc "Implement REST API endpoints"
maestro project add-task "$PROJECT" frontend -a ui-agent --deps "design" --desc "Build React components"
maestro project add-task "$PROJECT" database -a code-agent --deps "design" --desc "Create DB schema and migrations"
maestro project add-task "$PROJECT" e2e-test -a test-agent --deps "backend,frontend,database" --desc "End-to-end integration tests"
echo ""

# 3. 視覺化依賴圖
echo "--- Step 3: Dependency graph ---"
maestro project graph "$PROJECT"
echo ""

# 4. 查看可派發任務（只有 design 沒有依賴）
echo "--- Step 4: Ready tasks (only design) ---"
maestro project ready "$PROJECT"
echo ""

# 5. 執行 design
echo "--- Step 5: Complete design ---"
maestro project update "$PROJECT" design in-progress
maestro project result "$PROJECT" design "API spec: POST /users, GET /users/:id, PUT /users/:id. Schema: users(id, email, name, created_at)"
maestro project update "$PROJECT" design done
echo ""

# 6. design 完成後，三個任務同時就緒
echo "--- Step 6: Ready tasks (backend + frontend + database unlocked) ---"
maestro project ready "$PROJECT"
echo ""

# 7. 平行執行三個任務
echo "--- Step 7: Execute parallel tasks ---"
maestro project update "$PROJECT" backend in-progress
maestro project update "$PROJECT" frontend in-progress
maestro project update "$PROJECT" database in-progress
echo "  [3 agents working in parallel...]"

maestro project result "$PROJECT" database "Created users table with indexes. Migration 001_create_users.sql ready."
maestro project update "$PROJECT" database done

maestro project result "$PROJECT" backend "API endpoints implemented with validation. 8 unit tests pass."
maestro project update "$PROJECT" backend done

maestro project result "$PROJECT" frontend "Registration form + profile page. Storybook stories added."
maestro project update "$PROJECT" frontend done
echo ""

# 8. 所有前置完成，e2e-test 解鎖
echo "--- Step 8: Ready tasks (e2e-test unlocked) ---"
maestro project ready "$PROJECT"
echo ""

# 9. 執行整合測試
echo "--- Step 9: E2E testing ---"
maestro project update "$PROJECT" e2e-test in-progress
maestro project result "$PROJECT" e2e-test "All 15 E2E tests pass. Registration flow, profile update, and edge cases covered."
maestro project update "$PROJECT" e2e-test done
echo ""

# 10. 最終狀態
echo "--- Step 10: Final status ---"
maestro project status "$PROJECT"
echo ""

# 11. 執行紀錄
echo "--- Step 11: Execution log ---"
maestro project log "$PROJECT"
echo ""

echo "=== Demo Complete ==="
