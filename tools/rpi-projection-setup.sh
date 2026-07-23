#!/bin/bash
# One-time floor-projection setup ON the server Pi (root; safe to re-run).
# 2026-07-23: the renderer runs on the LEGACY display stack — a tiny
# firmware framebuffer at the render grid size (192x144) that the VideoCore
# scaler stretches to the projector's native mode. The KMS fb path spent
# ~60 ms/frame packing+upscaling in numpy on the 3B+, and GLES on vc4
# refused kmsdrm here (2026-07-22) — the firmware scaler is the free GPU.
# First run usually edits config.txt and asks for a reboot (exit 3).
set -euo pipefail
CFG=/boot/config.txt
[ -f "$CFG" ] || CFG=/boot/firmware/config.txt
CH=0

if grep -q '^dtoverlay=vc4-kms-v3d' "$CFG"; then
    sed -i 's|^dtoverlay=vc4-kms-v3d.*|#& # projection: legacy fb + GPU scaler|' "$CFG"
    CH=1
fi
if ! grep -q '^framebuffer_width=' "$CFG"; then
    printf '\n# floor projection: tiny fb, VideoCore scales to the projector\nframebuffer_width=192\nframebuffer_height=144\n' >> "$CFG"
    CH=1
fi
if grep -q '^gpu_mem_1024=16' "$CFG"; then
    sed -i 's/^gpu_mem_1024=16/gpu_mem_1024=64/' "$CFG"  # scaler headroom
    CH=1
fi
if grep -q '^hdmi_blanking=1' "$CFG"; then
    sed -i 's/^hdmi_blanking=1/hdmi_blanking=0/' "$CFG"  # never DPMS mid-show
    CH=1
fi
if [ "$CH" = 1 ]; then
    echo "display config updated in $CFG — REBOOT, then re-run this script"
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
