#!/usr/bin/env bash
# Start/stop the dev-box calibration stack (see calibrate_server.py header).
#   tools/calibrate/run-calibrate.sh          # start plumbing ssh + server
#   tools/calibrate/run-calibrate.sh stop
#   tools/calibrate/run-calibrate.sh status
# One ssh session does both directions: -R publishes the app on the Pi at
# 192.168.252.231:5001 (phone side; Pi sshd has GatewayPorts clientspecified,
# set 2026-08-30) and -L forwards every node's ESPHome API back here as
# localhost:1<port>. Logs + pids in ~/lohp/calibrate-run/.
set -euo pipefail
cd "$(dirname "$0")/../.."
RUN="$HOME/lohp/calibrate-run"
mkdir -p "$RUN"

stop_one() {
    local pidfile="$RUN/$1.pid"
    if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
        kill -TERM -- "-$(cat "$pidfile")" 2>/dev/null || kill "$(cat "$pidfile")" 2>/dev/null
        echo "$1 stopped"
    fi
    rm -f "$pidfile"
}

case "${1:-start}" in
  stop)   stop_one ssh; stop_one app; exit 0 ;;
  status)
    for n in ssh app; do
        if [[ -f "$RUN/$n.pid" ]] && kill -0 "$(cat "$RUN/$n.pid")" 2>/dev/null; then
            echo "$n running (pid $(cat "$RUN/$n.pid"))"
        else
            echo "$n NOT running"
        fi
    done
    exit 0 ;;
esac

stop_one ssh; stop_one app

FWDS=$(python3 - <<'PY'
import json
cfg = json.load(open('node_audio_config.json'))
print(' '.join('-L 1{p}:{h}:{p}'.format(p=e['port'], h=e['host'])
               for e in cfg['rooms'].values()))
PY
)
nohup setsid bash -c "while true; do ssh -p 2222 -N \
  -o BatchMode=yes -o ServerAliveInterval=15 -o ServerAliveCountMax=3 \
  -o StrictHostKeyChecking=accept-new \
  -R 0.0.0.0:5001:localhost:5001 $FWDS dietpi@localhost; sleep 5; done" \
  >"$RUN/ssh.log" 2>&1 &
echo $! > "$RUN/ssh.pid"

nohup setsid sim/.venv/bin/python tools/calibrate/calibrate_server.py \
  >"$RUN/app.log" 2>&1 &
echo $! > "$RUN/app.pid"

echo "started — phone: http://192.168.252.231:5001/calibrate (LOHP-ESP)"
