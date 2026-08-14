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

# Sync system time from the RTC the moment the kernel registers it, even if
# the base image lacks the Raspbian udev hwclock hook (harmless if it exists
# too). A udev rule, not a boot unit: the DS3231 probes ~7 s into boot,
# after sysinit has evaluated unit conditions (seen live 2026-08-12: a
# ConditionPathExists=/dev/rtc0 unit was skipped at 6.2 s, rtc0 appeared at
# 7.7 s). The kernel's own hctosys also fires at probe; belt and braces.
systemctl disable --now lohp-hwclock.service 2>/dev/null || true
rm -f /etc/systemd/system/lohp-hwclock.service   # old race-prone unit
cat > /etc/udev/rules.d/85-lohp-hwclock.rules <<'EOF'
ACTION=="add", SUBSYSTEM=="rtc", KERNEL=="rtc0", RUN+="/sbin/hwclock --hctosys --utc --rtc=/dev/rtc0"
EOF
udevadm control --reload 2>/dev/null || true

# --- services -----------------------------------------------------------
cp "$SRV/tools/lohp-projector-power.service" /etc/systemd/system/
cp "$SRV/tools/lohp-projector-shutdown.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable lohp-projector-power.service \
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
