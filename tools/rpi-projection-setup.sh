#!/bin/bash
# One-time lava-projection setup ON the server Pi (root; safe to re-run).
# The renderer needs the vc4 KMS driver — DietPi ships with it off, so the
# first run usually appends the overlay and asks for a reboot (exit 3).
set -euo pipefail
CFG=/boot/config.txt
[ -f "$CFG" ] || CFG=/boot/firmware/config.txt

if [ ! -e /dev/dri/card0 ] && [ ! -e /dev/dri/card1 ]; then
    if ! grep -q '^dtoverlay=vc4-kms-v3d' "$CFG"; then
        printf '\n# lava projection: KMS video for projection_renderer.py\ndtoverlay=vc4-kms-v3d\n' >> "$CFG"
        echo "KMS overlay added to $CFG — REBOOT, then re-run this script"
    else
        echo "KMS overlay already in $CFG but /dev/dri absent — reboot pending?"
    fi
    exit 3
fi

# numpy via apt; the renderer writes /dev/fb0 directly (no SDL/EGL — the
# vc4 EGL stack refused kmsdrm on the 3B+, and fewer layers is better here)
apt-get install -y python3-venv python3-numpy >/dev/null
grep -qs 'include-system-site-packages = true' /opt/lohp-projection-venv/pyvenv.cfg \
    || rm -rf /opt/lohp-projection-venv
[ -d /opt/lohp-projection-venv ] || python3 -m venv --system-site-packages /opt/lohp-projection-venv
/opt/lohp-projection-venv/bin/pip install -q -r /home/dietpi/lohp-server/tools/projection-requirements.txt
cp /home/dietpi/lohp-server/tools/lohp-projection.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable lohp-projection.service
systemctl restart lohp-projection.service
sleep 3
systemctl is-active --quiet lohp-projection.service \
    && echo "lava projection running (demo mode) — check the projector" \
    || { echo "service failed:"; journalctl -u lohp-projection -n 20 --no-pager; exit 1; }
