#!/usr/bin/env bash
# Sync this repo to the server Pi and (re)start the dockerized server.
#   tools/deploy-rpi.sh                  # default target: lohp-server.local (mDNS)
#   tools/deploy-rpi.sh 192.168.1.42     # or the IP once known
# The Pi side comes from the DietPi image prepared 2026-07-22 (pi-notes.md):
# root ssh with the bench box's ed25519 key, Docker installed on first boot.
set -euo pipefail
HOST=${1:-lohp-server.local}
DEST=/home/dietpi/lohp-server
SSH_OPTS=(-o StrictHostKeyChecking=accept-new)
cd "$(dirname "$0")/.."

rsync -az --delete --info=stats1 -e "ssh ${SSH_OPTS[*]}" \
    --exclude .git --exclude __pycache__ --exclude '*.pyc' \
    --exclude sim/.venv --exclude sim/sim.log --exclude sim/sim.pid \
    --filter 'protect /photos/***' --exclude /photos \
    ./ "root@$HOST:$DEST/"

ssh "${SSH_OPTS[@]}" "root@$HOST" "bash $DEST/tools/rpi-setup.sh"

printf 'health: '
curl -fsS --max-time 5 "http://$HOST:5000/api/health" && echo
echo "control panel: http://$HOST:5000/"
echo "sim RPI dot: green now; if not using mDNS run the sim with RPI_HOST=$HOST"
