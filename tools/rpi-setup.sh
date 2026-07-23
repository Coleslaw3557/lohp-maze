#!/bin/bash
# Runs ON the server Pi as root (invoked by tools/deploy-rpi.sh after rsync).
# Installs the systemd unit, builds the compose image, (re)starts the stack.
set -euo pipefail
cd /home/dietpi/lohp-server

# Docker comes from the SD image's first-boot script; self-heal if missing
if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
fi

cp tools/lohp-server.service /etc/systemd/system/lohp-server.service
systemctl daemon-reload
systemctl enable lohp-server.service

docker compose build
systemctl restart lohp-server.service

for _ in $(seq 1 60); do
    if curl -fsS --max-time 2 http://localhost:5000/api/health >/dev/null 2>&1; then
        echo "lohp-server healthy"
        exit 0
    fi
    sleep 2
done
echo "lohp-server not healthy after 120 s — check: docker logs lohp-server" >&2
exit 1
