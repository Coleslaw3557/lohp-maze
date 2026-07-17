#!/usr/bin/env bash
# Stop a background simulator started with ./run.sh -d
cd "$(dirname "$0")"
if [ -f sim.pid ] && kill -0 "$(cat sim.pid)" 2>/dev/null; then
    kill "$(cat sim.pid)" && rm -f sim.pid && echo "[sim] stopped"
else
    pkill -f 'sim/run_server.py|[.]venv/bin/python run_server.py' 2>/dev/null && echo "[sim] stopped (by pattern)" || echo "[sim] not running"
    rm -f sim.pid
fi
