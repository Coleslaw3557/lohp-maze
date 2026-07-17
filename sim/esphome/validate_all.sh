#!/usr/bin/env bash
# Validate every room node config (no compile). Fast sanity check for CI/pre-flash.
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
    python3 -m venv .venv
    .venv/bin/pip -q install esphome aioesphomeapi
fi
fail=0
for f in rooms/*.yaml; do
    if .venv/bin/esphome config "$f" > /dev/null 2>&1; then
        echo "OK    $f"
    else
        echo "FAIL  $f"
        fail=1
    fi
done
exit $fail
