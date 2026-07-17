#!/usr/bin/env bash
# Build & run one virtual sensor node natively (ESPHome host platform).
# Usage: ./run_node.sh entrance          (foreground; Ctrl-C stops)
#        ./run_node.sh entrance -d       (background daemon; log: node-<room>.log)
# First run creates ./.venv and compiles — a few minutes; later runs are fast.
#
# Daemon mode compiles, then execs the built binary directly instead of leaving
# an `esphome run` wrapper attached — a wrapper without a terminal can stall the
# node's event loop for seconds at a time (observed 2026-07-17).
set -euo pipefail
cd "$(dirname "$0")"
NODE="${1:?usage: ./run_node.sh <room-slug> [-d]  (see rooms/*.yaml)}"

if [ ! -d .venv ]; then
    echo "[esphome] creating venv + installing esphome (one-time, ~2 min)..."
    python3 -m venv .venv
    .venv/bin/pip -q install esphome aioesphomeapi
fi

if [ "${2:-}" = "-d" ]; then
    .venv/bin/esphome compile "rooms/${NODE}.yaml"
    BIN="rooms/.esphome/build/lohp-node-${NODE}/.pioenvs/lohp-node-${NODE}/program"
    nohup "$BIN" > "node-${NODE}.log" 2>&1 &
    echo "[esphome] node ${NODE} running (pid $!) — log: node-${NODE}.log"
else
    exec .venv/bin/esphome run "rooms/${NODE}.yaml"
fi
