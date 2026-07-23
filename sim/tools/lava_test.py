#!/usr/bin/env python3
"""Headless test of the Cuddle lava engine (projection_engine.py).

Runs against the real maze_layout.json geometry: mask sanity, stone
placement, presence/fade, the mischief mechanic (a walker marching at a
stone provokes sink + rise), timeout, and a perf budget check.

    sim/.venv/bin/python sim/tools/lava_test.py
"""
import base64
import json
import math
import os
import sys
import time

SIM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_DIR = os.path.dirname(SIM_DIR)
sys.path.insert(0, REPO_DIR)

import numpy as np  # noqa: E402
from projection_engine import (LavaShow, STONE_N, STONE_MIN_SPACE_M,  # noqa: E402
                               STONE_R_M)

FAIL = 0


def check(ok, label, detail=''):
    global FAIL
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        FAIL = 1


def main():
    layout = json.load(open(os.path.join(SIM_DIR, 'maze_layout.json')))
    eng = LavaShow(layout)

    print("1) geometry")
    frac = float(eng.mask.mean())
    # lit deck is ~5.5 m2 of the 7.26 m2 image rectangle => ~0.76 fill
    check(0.60 < frac < 0.88, f"deck mask fills {frac:.2f} of the image rect")
    wx, wz = eng._px_to_world(*eng.to_px(10.0, 1.0))
    check(abs(wx - 10.0) < 1e-6 and abs(wz - 1.0) < 1e-6, "world<->image round-trip")

    print("2) stones: a walkable chain across the deck")
    up = [s for s in eng.stones if s.state == 'up']
    down = [s for s in eng.stones if s.state == 'down']
    check(4 <= len(up) <= STONE_N and len(down) == 1,
          f"{len(up)} chain stones up + {len(down)} spare down")
    on_deck = all(eng.mask[int(s.py), int(s.px)] > 0.9 for s in eng.stones)
    check(on_deck, "every stone on the lit deck")
    gaps = [math.hypot(a.wx - b.wx, a.wz - b.wz) for a, b in zip(up, up[1:])]
    check(all(0.44 <= g <= 0.95 for g in gaps),
          f"stride gaps {min(gaps):.2f}–{max(gaps):.2f} m (walk-across-able)")
    span = max(s.wx for s in up) - min(s.wx for s in up)
    check(span >= 1.5, f"chain spans the crossing ({span:.2f} m east–west)")
    worst = min(math.hypot(a.wx - b.wx, a.wz - b.wz)
                for i, a in enumerate(eng.stones) for b in eng.stones[i + 1:])
    check(worst >= 0.44, f"min spacing {worst:.2f} m")

    print("3) presence / fade")
    check(eng.fade == 0.0 and not eng.active, "starts dark")
    eng.set_tracks([{'id': 'w', 'x': 10.0, 'z': 1.0}])
    for _ in range(40):
        eng.step(0.05)
    check(eng.active and eng.fade == 1.0, "presence brings the show up")
    frame = eng.render()
    check(frame.max() > 60, f"lava renders (max px {frame.max()})")
    # textured rock is mottled but grey-preserving: judge the 5x5 median so a
    # crack vein or carve groove under the exact center can't skew it
    sy, sx = int(up[2].py), int(up[2].px)
    med = np.median(frame[sy - 2:sy + 3, sx - 2:sx + 3].reshape(-1, 3), axis=0).astype(int)
    check(int(med.max() - med.min()) <= 16 and med[0] > 60,
          f"idle stone reads GREY rock (5x5 median {tuple(med)})")
    tex = eng.hello_patches()
    ok = (len(tex['stones']) == len(eng.stones)
          and all(len(base64.b64decode(t['rgba'])) == t['w'] * t['h'] * 4
                  for t in tex['stones'] + [tex['island']]))
    check(ok, f"rock textures exported ({len(tex['stones'])} stones + altar)")
    heat = base64.b64decode(eng.heat_b64())
    check(len(heat) == (eng.gh // 2) * (eng.gw // 2), "heat stream size")

    print("4) mischief: walk at a stone -> it sinks, another rises")
    # pick an approach angle whose walk line passes no OTHER up stone, so the
    # heading cone can only ever elect the intended target
    def seg_dist(px, pz, ax, az, bx, bz):
        vx, vz = bx - ax, bz - az
        t = max(0.0, min(1.0, ((px - ax) * vx + (pz - az) * vz) / (vx * vx + vz * vz)))
        return math.hypot(px - (ax + t * vx), pz - (az + t * vz))

    target, sx, sz = None, 0.0, 0.0
    for cand in up:
        for k in range(24):
            a = k * math.tau / 24
            ax, az = cand.wx + 1.5 * math.cos(a), cand.wz + 1.5 * math.sin(a)
            if all(o is cand or seg_dist(o.wx, o.wz, ax, az, cand.wx, cand.wz) > 0.6
                   for o in up):
                target, sx, sz = cand, ax, az
                break
        if target:
            break
    check(target is not None, "found a clear approach line")
    vx, vz = (target.wx - sx) / 1.5 * 0.6, (target.wz - sz) / 1.5 * 0.6
    events = []
    for i in range(60):  # 6 s budget
        eng.set_tracks([{'id': 'w', 'x': sx + vx * i * 0.1, 'z': sz + vz * i * 0.1}])
        eng.step(0.1)
        events += [e for e in eng.state()['events'] if e['e'] in ('sink', 'rise')]
        if any(e['e'] == 'rise' for e in events):
            break
    sinks = [e for e in events if e['e'] == 'sink']
    rises = [e for e in events if e['e'] == 'rise']
    check(len(sinks) == 1, f"exactly one sink ({len(sinks)})",
          f"stone {sinks[0]['id']}" if sinks else '')
    check(len(rises) == 1, "a replacement rises")
    check(bool(sinks) and sinks[0]['id'] == target.sid,
          "the sunk stone is the one being walked at")

    print("5) absence timeout")
    for _ in range(int(eng.timeout_s / 2) + 4):
        eng.step(2.0)
    check(not eng.active and eng.fade == 0.0, "show off after timeout")
    check(int(eng.render().max()) == 0, "renders black when off")

    print("6) perf (dev-box proxy; Pi 3B+ budget is ~4x this)")
    eng.set_tracks([{'id': 'w', 'x': 10.0, 'z': 1.0}])
    for _ in range(20):
        eng.step(0.05)
    t0 = time.perf_counter()
    n = 200
    for _ in range(n):
        eng.set_tracks([{'id': 'w', 'x': 10.0, 'z': 1.0}])
        eng.step(1 / 30)
        eng.render()
    ms = (time.perf_counter() - t0) / n * 1000
    check(ms < 25, f"step+render {ms:.1f} ms/frame at {eng.gw}x{eng.gh}")

    print("ALL PASS" if not FAIL else "FAILURES")
    sys.exit(FAIL)


if __name__ == '__main__':
    main()
