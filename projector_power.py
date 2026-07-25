#!/usr/bin/env python3
"""LS625X projector power control over RS232 — night on, day off, no internet.

The Cuddle projector's USB service port has no runtime control (probed
2026-07-23, see pi-notes.md), so power runs over its RS232 DE-9 via a USB
serial adapter. Frames are from the ViewSonic LS625X user manual RS232
command table (pages 70-82): 115200 8N1, write commands answered with an
ACK, the power-status read answered with a 9-byte frame whose 8th byte is
0=standby 1=warming 2=on 3=cooling. Checksum = sum of all bytes after the
first, mod 256.

Day/night comes from local solar geometry (NOAA solar position equations)
at Black Rock City — needs only a correct clock (DS3231 RTC; the Pi has no
battery clock of its own and the playa has no internet/NTP). Rule per Tim's
spec: projector ON from civil dusk (sun 6 deg below horizon, evening) until
sunrise, OFF otherwise. The asymmetry is handled by the solar hour angle:
mornings compare against the sunrise elevation, evenings against civil dusk.

Runs as two systemd units (tools/):
  lohp-projector-power.service    --daemon: reconcile at boot + every 20 min
  lohp-projector-shutdown.service --off at Pi shutdown (graceful projector off)

Touch .projector-manual next to this file to suspend reconciling (remote/
bench work); the shutdown OFF still applies. If the clock looks unset
(year < 2026: dead RTC battery / never initialized) the reconciler takes no
action at all rather than act on garbage time.
"""
import argparse
import datetime as dt
import fcntl
import glob
import math
import os
import select
import sys
import termios
import time
import tty

# Black Rock City (longitude east-positive)
LAT = float(os.environ.get('PROJ_LAT', '40.786'))
LON = float(os.environ.get('PROJ_LON', '-119.204'))
CHECK_SEC = int(os.environ.get('PROJ_CHECK_SEC', '1200'))
TRANSITION_RECHECK_SEC = 60
SUNRISE_ELEV = -0.833   # official sunrise/sunset (refraction + solar radius)
DUSK_ELEV = -6.0        # civil dusk
MIN_SANE_YEAR = 2026

OVERRIDE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             '.projector-manual')

# ViewSonic LS625X frames (user manual pages 70-82)
CMD_ON = bytes.fromhex('0614000400341100005d')
CMD_OFF = bytes.fromhex('0614000400341101005e')
CMD_STATUS = bytes.fromhex('071400050034000011005e')
ACK = bytes.fromhex('031400000014')
STATE_NAMES = {0: 'standby', 1: 'warming', 2: 'on', 3: 'cooling'}


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------- solar ----

def solar_position(now_utc):
    """Sun elevation (deg) and hour angle (deg, <0 morning) — NOAA equations."""
    doy = now_utc.timetuple().tm_yday
    frac_hour = now_utc.hour + now_utc.minute / 60 + now_utc.second / 3600
    g = 2 * math.pi / 365 * (doy - 1 + (frac_hour - 12) / 24)
    eqtime = 229.18 * (0.000075 + 0.001868 * math.cos(g)
                       - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g)
                       - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g)
            - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
            - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    tst = frac_hour * 60 + eqtime + 4 * LON  # true solar time, minutes
    ha = tst / 4 - 180
    if ha < -180:
        ha += 360
    lat_r = math.radians(LAT)
    cos_zen = (math.sin(lat_r) * math.sin(decl)
               + math.cos(lat_r) * math.cos(decl) * math.cos(math.radians(ha)))
    elevation = 90 - math.degrees(math.acos(max(-1, min(1, cos_zen))))
    return elevation, ha


def is_night(now_utc):
    """True between civil dusk and sunrise (the projector-on window)."""
    elev, ha = solar_position(now_utc)
    if ha < 0:  # morning side: night lasts until sunrise
        return elev < SUNRISE_ELEV
    return elev < DUSK_ELEV  # evening side: night starts at civil dusk


def clock_sane(now_utc):
    return now_utc.year >= MIN_SANE_YEAR


# --------------------------------------------------------------- serial ----

def find_port():
    if os.environ.get('PROJ_PORT'):
        return os.environ['PROJ_PORT']
    byid = sorted(glob.glob('/dev/serial/by-id/*'))
    for p in byid:  # prefer FTDI if several adapters ever coexist
        if 'FTDI' in p:
            return p
    if byid:
        return byid[0]
    usb = sorted(glob.glob('/dev/ttyUSB*'))
    return usb[0] if usb else None


class Projector:
    def __init__(self, path):
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        tty.setraw(self.fd)
        a = termios.tcgetattr(self.fd)
        a[2] = ((a[2] & ~termios.PARENB & ~termios.CSTOPB & ~termios.CSIZE)
                | termios.CS8 | termios.CREAD | termios.CLOCAL)
        a[4] = a[5] = termios.B115200
        termios.tcsetattr(self.fd, termios.TCSANOW, a)
        termios.tcflush(self.fd, termios.TCIOFLUSH)

    def close(self):
        os.close(self.fd)

    def _collect(self, want_status, timeout):
        """Read until an ACK / valid status frame shows up or time runs out."""
        buf = b''
        end = time.monotonic() + timeout
        got_ack = False
        while time.monotonic() < end:
            r, _, _ = select.select([self.fd], [], [], 0.05)
            if r:
                try:
                    buf += os.read(self.fd, 64)
                except BlockingIOError:
                    pass
            i = 0
            while i + 6 <= len(buf):
                if buf[i:i + 6] == ACK:
                    got_ack = True
                    if not want_status:
                        return 'ack'
                    buf = buf[:i] + buf[i + 6:]
                    continue
                if (buf[i] == 0x05 and i + 9 <= len(buf)
                        and buf[i + 1] == 0x14
                        and buf[i + 2:i + 7] == b'\x00\x03\x00\x00\x00'
                        and (sum(buf[i + 1:i + 8]) & 0xFF) == buf[i + 8]):
                    return buf[i + 7]
                i += 1
        return 'ack' if got_ack else None

    def _xact(self, frame, want_status):
        for _ in range(3):
            termios.tcflush(self.fd, termios.TCIFLUSH)
            os.write(self.fd, frame)
            got = self._collect(want_status, 0.7)
            if got is not None and (not want_status or got != 'ack'):
                return got
            time.sleep(0.2)
        return None

    def status(self):
        """0 standby / 1 warming / 2 on / 3 cooling, or None if unreachable."""
        s = self._xact(CMD_STATUS, want_status=True)
        return s if isinstance(s, int) else None

    def power(self, on):
        return self._xact(CMD_ON if on else CMD_OFF, want_status=False) == 'ack'


def open_projector():
    path = find_port()
    if path is None:
        return None, 'no-serial-adapter'
    try:
        return Projector(path), path
    except OSError as e:
        return None, f'{path}: {e.strerror}'


def usb_service_port_present():
    """The projector's own USB device (TI DDP442X) — free power telemetry."""
    for d in glob.glob('/sys/bus/usb/devices/*/idProduct'):
        try:
            with open(d) as f:
                if f.read().strip() != '4421':
                    continue
            with open(d.replace('idProduct', 'idVendor')) as f:
                if f.read().strip() == '0451':
                    return True
        except OSError:
            pass
    return False


# ------------------------------------------------------------ reconcile ----

def reconcile():
    """One pass: converge projector power to the day/night rule.

    Returns seconds until the next pass should run.
    """
    now = dt.datetime.now(dt.timezone.utc)
    if not clock_sane(now):
        log(f'projector: clock INSANE ({now:%Y-%m-%d}) — RTC unset/dead, '
            'taking no action')
        return CHECK_SEC
    night = is_night(now)
    elev, _ = solar_position(now)
    usb = 'present' if usb_service_port_present() else 'absent'

    proj, where = open_projector()
    if proj is None:
        log(f'projector: sun={elev:+.1f}deg {"night" if night else "day"} '
            f'usb={usb} serial UNAVAILABLE ({where})')
        return CHECK_SEC
    try:
        st = proj.status()
        name = STATE_NAMES.get(st, f'?{st}')
        if st is None:
            log(f'projector: sun={elev:+.1f}deg '
                f'{"night" if night else "day"} usb={usb} '
                f'NO RESPONSE on {where} (cable? null-modem? standby-RS232?)')
            return CHECK_SEC
        if os.path.exists(OVERRIDE_FILE):
            log(f'projector: sun={elev:+.1f}deg '
                f'{"night" if night else "day"} state={name} usb={usb} '
                'manual override — not touching')
            return CHECK_SEC
        if st in (1, 3):  # warming/cooling: let it finish, look again soon
            log(f'projector: sun={elev:+.1f}deg '
                f'{"night" if night else "day"} state={name} usb={usb} '
                'in transition')
            return TRANSITION_RECHECK_SEC
        action = 'none'
        if night and st == 0:
            action = 'power-on' if proj.power(True) else 'power-on FAILED'
        elif not night and st == 2:
            action = 'power-off' if proj.power(False) else 'power-off FAILED'
        log(f'projector: sun={elev:+.1f}deg {"night" if night else "day"} '
            f'state={name} usb={usb} action={action}')
        return TRANSITION_RECHECK_SEC if action.startswith('power') \
            else CHECK_SEC
    finally:
        proj.close()


def cmd_daemon():
    log(f'projector power reconciler: lat={LAT} lon={LON} '
        f'check every {CHECK_SEC}s, on from civil dusk to sunrise')
    while True:
        try:
            delay = reconcile()
        except Exception as e:  # keep the loop alive; systemd logs it
            log(f'projector: reconcile error: {e!r}')
            delay = CHECK_SEC
        time.sleep(delay)


def cmd_power(on):
    proj, where = open_projector()
    if proj is None:
        log(f'projector: cannot send power-{"on" if on else "off"} '
            f'({where})')
        return 0 if not on else 1  # never block a shutdown on a missing cable
    try:
        ok = proj.power(on)
        log(f'projector: power-{"on" if on else "off"} '
            f'{"acked" if ok else "NO ACK"} on {where}')
        return 0 if ok else 1
    finally:
        proj.close()


def cmd_status():
    proj, where = open_projector()
    if proj is None:
        log(f'serial unavailable: {where}')
        return 1
    try:
        st = proj.status()
        log(f'{where}: state={STATE_NAMES.get(st, st)}')
        return 0 if st is not None else 1
    finally:
        proj.close()


def cmd_test_solar():
    now = dt.datetime.now(dt.timezone.utc)
    pdt = dt.timezone(dt.timedelta(hours=-7), 'PDT')
    elev, ha = solar_position(now)
    log(f'now: {now:%Y-%m-%d %H:%M} UTC / {now.astimezone(pdt):%H:%M} PDT  '
        f'sun={elev:+.1f}deg ha={ha:+.1f}deg -> '
        f'{"NIGHT (projector on)" if is_night(now) else "DAY (projector off)"}'
        f'{"" if clock_sane(now) else "  [CLOCK INSANE — daemon would hold]"}')
    prev = is_night(now)
    t = now
    for _ in range(26 * 30):  # scan 26 h in 2-min steps
        t += dt.timedelta(minutes=2)
        cur = is_night(t)
        if cur != prev:
            log(f'  {"dusk  -> ON " if cur else "sunrise -> OFF"}: '
                f'{t:%Y-%m-%d %H:%M} UTC / {t.astimezone(pdt):%H:%M} PDT')
            prev = cur
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    m = ap.add_mutually_exclusive_group(required=True)
    m.add_argument('--daemon', action='store_true',
                   help='reconcile at start and every 20 min (systemd unit)')
    m.add_argument('--once', action='store_true', help='single reconcile pass')
    m.add_argument('--on', action='store_true', help='send power on')
    m.add_argument('--off', action='store_true',
                   help='send graceful power off (used at Pi shutdown)')
    m.add_argument('--status', action='store_true', help='read power state')
    m.add_argument('--test-solar', action='store_true',
                   help='show current day/night verdict and next transitions')
    a = ap.parse_args()
    if a.daemon:
        cmd_daemon()
    elif a.once:
        reconcile()
        return 0
    elif a.on:
        return cmd_power(True)
    elif a.off:
        return cmd_power(False)
    elif a.status:
        return cmd_status()
    elif a.test_solar:
        return cmd_test_solar()


if __name__ == '__main__':
    sys.exit(main())
