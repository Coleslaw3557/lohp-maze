#!/usr/bin/env python3
"""Solid-color ArtDMX probe for the camp-sign bridge — strip color-order check.

Determines the real SIGN_COLOR_ORDER (sign_config.h) without opening the box:
unicasts ArtDMX frames straight at lohp-sign-bridge.local with every zone set
to one pure color, same packet shape the server sends.

    ./strip_probe.py cycle          # RED / GREEN / BLUE, 4 s each, forever
    ./strip_probe.py red            # hold one color (red/green/blue/white/off)
    ./strip_probe.py cycle --host 192.168.1.x   # if .local doesn't resolve

Reading the result: the three colors you SEE during RED, GREEN, BLUE — in that
order — spell the constant. See blue,red,green -> BRG. See red,green,blue ->
RGB is already right. Edit sign_config.h and `./build.sh ota`.

If the server is animating the sign (attract mode), stop that first — its 44 Hz
frames interleave with ours and the sign flickers between both. The 1 Hz static
heartbeat is fine: this probe sends 30 Hz and the last frame received wins.

Unicast only — never broadcast this: rooms share universe 0, and this frame
zeroes channels 1-160.

On Ctrl-C the server's heartbeat repaints the theme within ~1 s; with no server
running the sign falls to its amber breathe after 3 s. Both are normal.
"""

import argparse
import socket
import sys
import time

ZONE_COUNT = 24
ZONE_DMX_FIRST = 161  # zone k = 8-ch slot at 161 + 8k, layout tot/R/G/B/W/strobe
PORT = 6454

COLORS = {
    "red": (255, 0, 0),
    "green": (0, 255, 0),
    "blue": (0, 0, 255),
    "white": (255, 255, 255),
    "off": (0, 0, 0),
}


def frame(r, g, b):
    dmx = bytearray(512)
    for k in range(ZONE_COUNT):
        base = ZONE_DMX_FIRST - 1 + 8 * k
        dmx[base + 0] = 255  # total_dimming full; W and strobe stay 0
        dmx[base + 1] = r
        dmx[base + 2] = g
        dmx[base + 3] = b
    return dmx


def packet(dmx):
    head = bytearray(b"Art-Net\x00")
    head += bytes([0x00, 0x50])  # OpDmx
    head += bytes([0x00, 0x0E])  # protocol 14
    head += bytes([0x00, 0x00])  # sequence off, physical 0
    head += bytes([0x00, 0x00])  # universe 0, lo/hi
    head += bytes([len(dmx) >> 8, len(dmx) & 0xFF])
    return bytes(head) + bytes(dmx)


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("color", choices=sorted(COLORS) + ["cycle"])
    p.add_argument("--host", default="lohp-sign-bridge.local")
    p.add_argument("--rate", type=float, default=30.0, help="frames/s (default 30)")
    p.add_argument("--dwell", type=float, default=4.0, help="cycle: seconds per color")
    args = p.parse_args()

    try:
        ip = socket.gethostbyname(args.host)
    except socket.gaierror:
        sys.exit(f"cannot resolve {args.host} — pass --host <ip> (serial 'f' prints it)")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    gap = 1.0 / args.rate

    def blast(name, seconds=None):
        pkt = packet(frame(*COLORS[name]))
        end = None if seconds is None else time.monotonic() + seconds
        while end is None or time.monotonic() < end:
            sock.sendto(pkt, (ip, PORT))
            time.sleep(gap)

    print(f"[probe] -> {args.host} ({ip}):{PORT}, universe 0, zones @{ZONE_DMX_FIRST}")
    try:
        if args.color == "cycle":
            print("[probe] the colors you SEE for RED, GREEN, BLUE spell SIGN_COLOR_ORDER")
            while True:
                for name in ("red", "green", "blue"):
                    print(f"[probe] sending {name.upper()} — what color shows?")
                    blast(name, args.dwell)
        else:
            print(f"[probe] holding {args.color} — Ctrl-C to stop")
            blast(args.color)
    except KeyboardInterrupt:
        print("\n[probe] stopped — theme repaints on next server frame")


if __name__ == "__main__":
    main()
