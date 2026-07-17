#!/usr/bin/env bash
# Launch the LoHP maze simulator (real server + virtual DMX + 3D web UI).
# Usage: ./run.sh            foreground
#        ./run.sh -d         background (logs to sim/sim.log, pid in sim/sim.pid)
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
    echo "[sim] creating venv..."
    python3 -m venv .venv
    .venv/bin/pip -q install -r requirements.txt
fi

if [ "${1:-}" = "-d" ]; then
    if [ -f sim.pid ] && kill -0 "$(cat sim.pid)" 2>/dev/null; then
        echo "[sim] already running (pid $(cat sim.pid))"; exit 0
    fi
    nohup .venv/bin/python run_server.py >> sim.log 2>&1 &
    echo $! > sim.pid
    echo "[sim] started (pid $(cat sim.pid)) — UI: http://$(hostname -I | awk '{print $1}'):5001  log: sim/sim.log"
else
    exec .venv/bin/python run_server.py
fi
