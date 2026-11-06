#!/bin/bash
# ========================================================
#       Stop HMS Machine Interface Services (Linux)
# ========================================================

echo "Stopping HMS Machine Interface services..."

# 1. Kill process listening on port 1310
PORT_PID=$(lsof -t -i:1310 2>/dev/null || fuser 1310/tcp 2>/dev/null)
if [ -n "$PORT_PID" ]; then
    echo "[STOPPING] Terminating process on Port 1310 (PID: $PORT_PID)..."
    kill -9 $PORT_PID 2>/dev/null
else
    echo "[INFO] No process listening on Port 1310."
fi

# 2. Kill automate_results processes
WORKER_PIDS=$(pgrep -f "manage.py automate_results")
if [ -n "$WORKER_PIDS" ]; then
    echo "[STOPPING] Terminating Automation Worker (PID: $WORKER_PIDS)..."
    kill -9 $WORKER_PIDS 2>/dev/null
else
    echo "[INFO] No Automation Worker process found."
fi

# 3. Kill any start_all.sh background loops
LAUNCHER_PIDS=$(pgrep -f "start_all.sh")
if [ -n "$LAUNCHER_PIDS" ]; then
    kill -9 $LAUNCHER_PIDS 2>/dev/null
fi

echo "[COMPLETE] HMS Machine Interface services stopped."

