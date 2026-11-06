#!/bin/bash
# ========================================================
#       HMS Machine Interface Launcher (Linux)
# ========================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 1. Detect Python executable
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON_CMD="$SCRIPT_DIR/.venv/bin/python"
elif [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
elif command -v python3.11 >/dev/null 2>&1; then
    PYTHON_CMD="python3.11"
else
    PYTHON_CMD="python3"
fi

echo "Using Python: $($PYTHON_CMD --version)"

# Verify Python version (Django 3.2 requires Python <= 3.11)
$PYTHON_CMD -c "import sys; sys.exit(0 if sys.version_info < (3, 13) else 1)" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[WARNING] Detected Python 3.13+. Django 3.2 requires Python 3.10 or 3.11 due to cgi module removal."
fi

# 2. Ensure logs folder exists
mkdir -p logs

# Cleanup handler on exit (Ctrl+C or kill)
cleanup() {
    echo ""
    echo "Stopping HMS Machine Interface services..."
    kill $(jobs -p) 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

# 3. Start Django Server on Port 1310 in background
echo "[1/2] Starting Django Server on 0.0.0.0:1310..."
$PYTHON_CMD manage.py runserver 0.0.0.0:1310 >> logs/server.log 2>&1 &
SERVER_PID=$!
echo "      Django Server started (PID: $SERVER_PID, Logging to logs/server.log)"

sleep 2

# 4. Start Automation Worker with Auto-Restart Supervisor in background
echo "[2/2] Starting Automation Worker with Auto-Restart..."
(
    while true; do
        echo "[$(date)] Starting automate_results worker..." >> logs/automation.log
        $PYTHON_CMD manage.py automate_results >> logs/automation.log 2>&1
        EXIT_CODE=$?
        echo "[$(date)] Worker exited (code $EXIT_CODE). Restarting in 5 seconds..." >> logs/automation.log
        sleep 5
    done
) &
WORKER_PID=$!
echo "      Automation Worker started (PID: $WORKER_PID, Logging to logs/automation.log)"

echo ""
echo "======================================================="
echo "[SUCCESS] Both services are running in background!"
echo "  * Server URL      : http://localhost:1310/"
echo "  * Web UI Dashboard: http://localhost:1310/manual-entry/"
echo "  * Check status    : ./status.sh"
echo "  * Stop services   : ./stop_all.sh"
echo "======================================================="
echo "Press Ctrl+C to stop all services."
echo ""

# Wait for children
wait
