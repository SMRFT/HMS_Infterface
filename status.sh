#!/bin/bash
# ========================================================
#       HMS Machine Interface Status Diagnostic (Linux)
# ========================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Detect Python
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_CMD="$SCRIPT_DIR/.venv/bin/python"
elif [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
elif command -v python3.11 >/dev/null 2>&1; then
    PYTHON_CMD="python3.11"
else
    PYTHON_CMD="python3"
fi

echo "======================================================="
echo "       HMS Machine Interface Status Diagnostic (Linux)"
echo "======================================================="
echo ""

# 1. Port 1310 Check
PORT_PID=$(lsof -t -i:1310 2>/dev/null || fuser 1310/tcp 2>/dev/null)
if [ -n "$PORT_PID" ]; then
    echo "[ONLINE]  Django Server is LISTENING on port 1310 (PID: $PORT_PID)"
else
    echo "[OFFLINE] Django Server is NOT listening on port 1310"
fi

# 2. Worker Check
WORKER_PIDS=$(pgrep -f "manage.py automate_results")
if [ -n "$WORKER_PIDS" ]; then
    echo "[ONLINE]  Automation Worker is RUNNING (PID: $WORKER_PIDS)"
else
    echo "[OFFLINE] Automation Worker is NOT running"
fi

echo ""
echo "Checking Live Retry Queue in MongoDB..."
$PYTHON_CMD -c "import os, sys, dotenv; dotenv.load_dotenv(); sys.path.insert(0, '.'); from machine import retry_service; s = retry_service.get_queue_summary(); print('  * Waiting Approval: ' + str(s.get('WAITING_APPROVAL', 0)) + ' | Retrying: ' + str(s.get('PENDING_RETRY', 0)) + ' | Failed: ' + str(s.get('FAILED_PERMANENT', 0)) + ' | Resolved: ' + str(s.get('RESOLVED', 0)))" 2>/dev/null

echo ""
echo "Web UI Dashboard: http://localhost:1310/manual-entry/"
echo "======================================================="

