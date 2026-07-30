#!/usr/bin/env bash
# Launch the audio pool console — the web page for seeing, auditioning and
# filling each room action's sound pool (tools/audio_console.py).
#
# Usage: tools/audio-console.sh              foreground (Ctrl-C to stop)
#        tools/audio-console.sh -d           background (log: tools/audio-console.log)
#        tools/audio-console.sh --port 8080 --server http://lohp-server.local:5000
#
# Reuses the sim's virtualenv: same Quart pins as the production server.
set -euo pipefail
cd "$(dirname "$0")/.."
VENV=sim/.venv
PIDFILE=tools/audio-console.pid

if [ ! -d "$VENV" ]; then
    echo "[audio-console] creating sim venv..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" -q install -r sim/requirements.txt
fi

if [ "${1:-}" = "-d" ]; then
    shift
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
        echo "[audio-console] already running (pid $(cat "$PIDFILE"))"; exit 0
    fi
    # setsid so it survives the shell that launched it (sim/run.sh -d does not)
    setsid nohup "$VENV/bin/python" tools/audio_console.py "$@" \
        >> tools/audio-console.log 2>&1 &
    echo $! > "$PIDFILE"
    echo "[audio-console] started (pid $(cat "$PIDFILE")) — http://$(hostname -I | awk '{print $1}'):5055"
    echo "[audio-console] stop with: kill \$(cat $PIDFILE)"
else
    exec "$VENV/bin/python" tools/audio_console.py "$@"
fi
