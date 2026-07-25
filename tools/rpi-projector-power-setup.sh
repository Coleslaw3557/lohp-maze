#!/bin/bash
# One-time projector-power setup ON the server Pi (root; safe to re-run).
# Installs the LS625X RS232 power reconciler (projector_power.py) and the
# shutdown power-off hook, and enables I2C + the DS3231 real-time clock
# overlay (the playa has no internet, so the DS3231 is the clock of record;
# the Pi 3B+ has none of its own). Hardware can arrive later: the services
# tolerate a missing serial adapter / RTC and just log until they appear.
set -euo pipefail
CFG=/boot/config.txt
[ -f "$CFG" ] || CFG=/boot/firmware/config.txt
SRV=/home/dietpi/lohp-server
REBOOT_NEEDED=0

# --- I2C + DS3231 RTC overlay ------------------------------------------
if grep -q '^dtparam=i2c_arm=on' "$CFG"; then :
elif grep -q '^#dtparam=i2c_arm=on' "$CFG"; then
    sed -i 's/^#dtparam=i2c_arm=on/dtparam=i2c_arm=on/' "$CFG"
    REBOOT_NEEDED=1
else
    printf '\n# projector power: DS3231 RTC (playa has no NTP)\ndtparam=i2c_arm=on\n' >> "$CFG"
    REBOOT_NEEDED=1
fi
if ! grep -q '^dtoverlay=i2c-rtc,ds3231' "$CFG"; then
    printf 'dtoverlay=i2c-rtc,ds3231\n' >> "$CFG"
    REBOOT_NEEDED=1
fi

# Sync system time from the RTC at boot even if the base image lacks the
# Raspbian udev hwclock hook. Harmless if the hook exists too.
cat > /etc/systemd/system/lohp-hwclock.service <<'EOF'
[Unit]
Description=LOHP: set system clock from DS3231 at boot
ConditionPathExists=/dev/rtc0
DefaultDependencies=no
After=systemd-modules-load.service
Before=time-set.target sysinit.target
[Service]
Type=oneshot
ExecStart=/sbin/hwclock --hctosys --utc
[Install]
WantedBy=sysinit.target
EOF

# --- services -----------------------------------------------------------
cp "$SRV/tools/lohp-projector-power.service" /etc/systemd/system/
cp "$SRV/tools/lohp-projector-shutdown.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable lohp-hwclock.service lohp-projector-power.service \
    lohp-projector-shutdown.service
systemctl restart lohp-projector-power.service
systemctl start lohp-projector-shutdown.service

# --- report -------------------------------------------------------------
echo "--- status"
if [ -e /dev/rtc0 ]; then
    echo "RTC: $(hwclock -r 2>&1) (if wrong: get bench NTP time, then hwclock -w)"
else
    echo "RTC: /dev/rtc0 absent — module not plugged or reboot pending"
fi
ls /dev/serial/by-id/ 2>/dev/null | sed 's/^/serial: /' \
    || echo "serial: no USB serial adapter yet"
python3 "$SRV/projector_power.py" --test-solar
systemctl --no-pager --lines=3 status lohp-projector-power.service | tail -4
if [ "$REBOOT_NEEDED" = 1 ]; then
    echo "config.txt updated for I2C/RTC — REBOOT before the DS3231 works"
fi
