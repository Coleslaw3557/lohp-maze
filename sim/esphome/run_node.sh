#!/usr/bin/env bash
# Build & run one virtual sensor node natively (ESPHome host platform).
# Usage: ./run_node.sh entrance          (foreground; Ctrl-C stops)
# First run creates ./.venv and compiles — a few minutes; later runs are fast.
set -euo pipefail
cd "$(dirname "$0")"
NODE="${1:?usage: ./run_node.sh <room-slug>  (see rooms/*.yaml)}"

if [ ! -d .venv ]; then
    echo "[esphome] creating venv + installing esphome (one-time, ~2 min)..."
    python3 -m venv .venv
    .venv/bin/pip -q install esphome aioesphomeapi
fi

exec .venv/bin/esphome run "rooms/${NODE}.yaml"
