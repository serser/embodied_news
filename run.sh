#!/usr/bin/env bash
# Supervise app.py: relaunch whenever it exits (crash, OOM, port drop, etc.).
# Ctrl-C (SIGINT) and SIGTERM cleanly stop the child and break the loop.

set -u

PYTHON="/home/user/miniconda3/bin/python"
APP="app.py"
RESTART_DELAY=2

child_pid=""

shutdown() {
    trap - INT TERM
    if [[ -n "$child_pid" ]] && kill -0 "$child_pid" 2>/dev/null; then
        echo "[run.sh] Stopping app (pid $child_pid)..."
        sudo kill -TERM "$child_pid" 2>/dev/null || true
        wait "$child_pid" 2>/dev/null || true
    fi
    exit 0
}
trap shutdown INT TERM

cd "$(dirname "$0")"

while true; do
    echo "[run.sh] Starting: $PYTHON $APP"
    sudo "$PYTHON" "$APP" &
    child_pid=$!
    wait "$child_pid"
    exit_code=$?
    child_pid=""
    echo "[run.sh] app.py exited with code $exit_code; restarting in ${RESTART_DELAY}s..."
    sleep "$RESTART_DELAY"
done
