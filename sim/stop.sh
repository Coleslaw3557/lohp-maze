#!/usr/bin/env bash
# Stop a background simulator started with ./run.sh -d
# Note: SIGTERM alone doesn't fully stop the server — hypercorn's graceful
# handler shuts the API down but main.py keeps waiting on the websockets
# server forever (production docker relies on SIGKILL the same way) — so we
# escalate after a short grace period.
cd "$(dirname "$0")"
kill_wait() {
    local pid=$1
    kill "$pid" 2>/dev/null
    for _ in 1 2 3 4 5 6; do
        kill -0 "$pid" 2>/dev/null || return 0
        sleep 0.5
    done
    kill -9 "$pid" 2>/dev/null
    sleep 0.3
    ! kill -0 "$pid" 2>/dev/null
}

stopped=""
if [ -f sim.pid ] && kill -0 "$(cat sim.pid)" 2>/dev/null; then
    kill_wait "$(cat sim.pid)" && stopped=1
fi
# catch strays regardless
for pid in $(pgrep -f 'run_server\.py' 2>/dev/null); do
    kill_wait "$pid" && stopped=1
done
rm -f sim.pid
[ -n "$stopped" ] && echo "[sim] stopped" || echo "[sim] not running"
