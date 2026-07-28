#!/usr/bin/env bash
# Supervise app.py: relaunch whenever it exits (crash, OOM, port drop, etc.).
# Background poller `git pull`s every $PULL_INTERVAL seconds; if HEAD moved,
# it SIGTERMs the app so this loop respawns it with the new code.
# Ctrl-C (SIGINT) and SIGTERM cleanly stop both children and break the loop.

set -u

PYTHON="/home/user/miniconda3/bin/python"
APP="app.py"
RESTART_DELAY=2
PULL_INTERVAL="${PULL_INTERVAL:-1800}"  # 30 minutes

child_pid=""
poller_pid=""

shutdown() {
    trap - INT TERM
    if [[ -n "$poller_pid" ]] && kill -0 "$poller_pid" 2>/dev/null; then
        kill -TERM "$poller_pid" 2>/dev/null || true
        wait "$poller_pid" 2>/dev/null || true
    fi
    if [[ -n "$child_pid" ]] && kill -0 "$child_pid" 2>/dev/null; then
        echo "[run.sh] Stopping app (pid $child_pid)..."
        sudo kill -TERM "$child_pid" 2>/dev/null || true
        wait "$child_pid" 2>/dev/null || true
    fi
    exit 0
}
trap shutdown INT TERM

cd "$(dirname "$0")"

# Poll git in the background. When origin/main moves ahead, pull and kill the
# app; the main loop's `wait` unblocks and respawns with fresh code. All git
# failures are swallowed so a transient network flap never kills the server.
git_pull_loop() {
    local branch remote_ref
    branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo main)"
    remote_ref="origin/${branch}"
    while true; do
        sleep "$PULL_INTERVAL"
        if ! git fetch --quiet origin "$branch" 2>/dev/null; then
            echo "[run.sh] git fetch failed; will retry in ${PULL_INTERVAL}s"
            continue
        fi
        local local_head remote_head
        local_head="$(git rev-parse HEAD 2>/dev/null || true)"
        remote_head="$(git rev-parse "$remote_ref" 2>/dev/null || true)"
        if [[ -z "$local_head" || -z "$remote_head" || "$local_head" == "$remote_head" ]]; then
            continue
        fi
        echo "[run.sh] Detected upstream update: ${local_head:0:7} -> ${remote_head:0:7}"
        if ! git pull --ff-only --quiet origin "$branch"; then
            echo "[run.sh] git pull failed (dirty tree or non-fast-forward?); skipping restart"
            continue
        fi
        if [[ -n "$child_pid" ]] && kill -0 "$child_pid" 2>/dev/null; then
            echo "[run.sh] Restarting app to pick up new code..."
            sudo kill -TERM "$child_pid" 2>/dev/null || true
        fi
    done
}

git_pull_loop &
poller_pid=$!

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
