#!/usr/bin/env bash
# Sync this repo to the server Pi and (re)start the dockerized server.
#   tools/deploy-rpi.sh                  # default target: lohp-server.local (mDNS)
#   tools/deploy-rpi.sh 192.168.252.231  # or the IP (RUT DHCP reservation)
# Run from a machine on the maze LAN (join LOHP-ESP); from upstream WiFi the
# Pi sits behind the RUT140's NAT — see wiring-guides/maze-network.md.
# On-playa (2026-08-30) the Pi reverse-tunnels to the dev box instead:
#   SSH_PORT=2222 tools/deploy-rpi.sh localhost
# The Pi side comes from the DietPi image prepared 2026-07-22 (pi-notes.md):
# root ssh with the bench box's ed25519 key, Docker installed on first boot.
set -euo pipefail
HOST=${1:-lohp-server.local}
SSH_PORT=${SSH_PORT:-22}
DEST=/home/dietpi/lohp-server
SSH_OPTS=(-o StrictHostKeyChecking=accept-new -p "$SSH_PORT")
cd "$(dirname "$0")/.."

rsync -az --delete --info=stats1 -e "ssh ${SSH_OPTS[*]}" \
    --exclude .git --exclude __pycache__ --exclude '*.pyc' \
    --exclude sim/.venv --exclude sim/sim.log --exclude sim/sim.pid \
    --exclude sim/esphome/.venv --exclude sim/esphome/rooms/.esphome \
    --filter 'protect /photos/***' --exclude /photos \
    --filter 'protect /data/***' --exclude /data \
    --filter 'protect /audio_files/generated/***' --exclude /audio_files/generated \
    --filter 'protect /.floor_theme' --filter 'protect /.projector-manual' \
    ./ "root@$HOST:$DEST/"

ssh "${SSH_OPTS[@]}" "root@$HOST" "bash $DEST/tools/rpi-setup.sh"

# Health via ssh so it also works when $HOST is a tunnel endpoint whose :5000
# isn't forwarded.
printf 'health: '
ssh "${SSH_OPTS[@]}" "root@$HOST" 'curl -fsS --max-time 5 http://localhost:5000/api/health' && echo
echo "control panel: http://$HOST:5000/"
echo "sim RPI dot: green now; if not using mDNS run the sim with RPI_HOST=$HOST"
