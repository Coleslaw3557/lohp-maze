#!/usr/bin/env python3
"""Headless test of the Cuddle floor-show engines (projection_engine.py).

Runs against the real maze_layout.json geometry. Lava: mask sanity, stone
placement, presence/fade, the mischief mechanic (a walker marching at a
stone provokes sink + rise), Kukulkan, timeout, perf budget. Jungle: snakes
slither and flee feet, fireflies come out, textures, perf.

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
from projection_engine import (CARVED_FLAGS, JungleShow, LavaShow,  # noqa: E402
                               SNAKE_SPECS, STONE_N, STONE_MIN_SPACE_M,
                               STONE_R_M, TempleShow)

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
                  for t in tex['stones'] + [tex['island'], tex['monster']]))
    check(ok, f"textures exported ({len(tex['stones'])} stones + altar + monster head)")
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

    print("5) Kukulkan shows his head")
    eng2 = LavaShow(layout)
    eng2._monster['next'] = 1.0  # don't sit out the real 45–100 s gap
    seen = {'monster_swim': False, 'monster_breach': False, 'monster_sink': False}
    pose_seen, breach_xy = False, None
    for _ in range(400):  # 40 s of sim time, walker standing on the deck
        eng2.set_tracks([{'id': 'w', 'x': 9.2, 'z': 0.6}])
        eng2.step(0.1)
        st = eng2.state()
        pose_seen = pose_seen or bool(st['monster'])
        for e in st['events']:
            if e['e'] in seen:
                seen[e['e']] = True
                if e['e'] == 'monster_breach':
                    breach_xy = (e['x'], e['y'])
        if all(seen.values()):
            break
    check(all(seen.values()), f"swim → breach → sink all occurred ({seen})")
    check(pose_seen, "head pose streamed while surfaced")
    if breach_xy:
        wx, wz = eng2._px_to_world(*breach_xy)
        dmin = min(math.hypot(wx - s.wx, wz - s.wz)
                   for s in eng2.stones if s.state != 'down')
        check(dmin >= 0.5, f"breached clear of the stones ({dmin:.2f} m)")
        dw = math.hypot(wx - 9.2, wz - 0.6)
        check(dw >= 0.9, f"breached clear of the walker ({dw:.2f} m)")

    print("6) absence timeout")
    for _ in range(int(eng.timeout_s / 2) + 4):
        eng.step(2.0)
    check(not eng.active and eng.fade == 0.0, "show off after timeout")
    check(int(eng.render().max()) == 0, "renders black when off")

    print("7) perf (dev-box proxy; Pi 3B+ budget is ~4x this)")
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

    print("8) jungle theme: snakes on the deck")
    jng = JungleShow(layout)
    check(len(jng.snakes) == len(SNAKE_SPECS), f"{len(jng.snakes)} snakes placed")
    check(all(jng._on_deck(sn.x, sn.z) for sn in jng.snakes),
          "every snake head on the lit deck")
    check(len(jng.glyphs) >= 2, f"{len(jng.glyphs)} fallen glyph stones")
    heads0 = [(sn.x, sn.z) for sn in jng.snakes]
    jng.cue('test')
    for _ in range(100):  # 5 s, nobody around
        jng.step(0.05)
    moved = [math.hypot(sn.x - x0, sn.z - z0)
             for sn, (x0, z0) in zip(jng.snakes, heads0)]
    check(all(m > 0.25 for m in moved),
          f"snakes slither ({min(moved):.2f}–{max(moved):.2f} m in 5 s)")
    on_deck = all(jng._on_deck(x, z, thresh=0.3)
                  for sn in jng.snakes for x, z in sn.trail[:3])
    check(on_deck, "snake heads stay on the deck")

    print("9) jungle: feet spook a snake")
    prey = jng.snakes[0]
    wx, wz = prey.x + 0.15, prey.z
    fled = False
    for _ in range(80):  # 4 s standing right next to its head
        jng.set_tracks([{'id': 'w', 'x': wx, 'z': wz}])
        jng.step(0.05)
        fled = fled or any(e['e'] == 'snake_flee' and e['id'] == prey.sid
                           for e in jng.state()['events'])
    dist = math.hypot(prey.x - wx, prey.z - wz)
    check(fled, "snake_flee event fired")
    check(dist > 0.5, f"the snake got away ({dist:.2f} m from the feet)")

    print("10) jungle: fireflies come out")
    jng2 = JungleShow(layout)
    for _ in range(200):  # 20 s, walker standing on the deck
        jng2.set_tracks([{'id': 'w', 'x': 9.6, 'z': 1.0}])
        jng2.step(0.1)
    lit_seen = any(f['on'] for f in jng2.flies)
    check(len(jng2.flies) > 0, f"fireflies out ({len(jng2.flies)})")
    check(lit_seen or len(jng2.flies) > 2, "fireflies blink")

    print("11) jungle: textures + render")
    tex = jng.hello_patches()
    ok = (all(len(base64.b64decode(t['rgba'])) == t['w'] * t['h'] * 4
              for t in [tex['island']] + tex['glyphs'])
          and len(tex['snakes']) == len(jng.snakes)
          and all(len(s['colors']) == len(s['w']) for s in tex['snakes']))
    check(ok, f"textures exported (altar + {len(tex['glyphs'])} glyphs "
              f"+ {len(tex['snakes'])} snake styles)")
    frame = jng.render()
    check(frame.max() > 40, f"jungle renders (max px {frame.max()})")
    lit = frame[jng.mask > 0.9].astype(int)
    check(lit[:, 1].mean() > lit[:, 0].mean() and lit[:, 1].mean() > lit[:, 2].mean(),
          "the floor reads GREEN (jungle, not lava)")
    st = jng.state()
    check(all(len(s['pts']) <= sn.n_seg for s, sn in zip(st['snakes'], jng.snakes)),
          "spine streams bounded by segment count")

    print("12) jungle perf (dev-box proxy; Pi 3B+ budget is ~4x this)")
    t0 = time.perf_counter()
    n = 200
    for _ in range(n):
        jng.set_tracks([{'id': 'w', 'x': 10.0, 'z': 1.0}])
        jng.step(1 / 30)
        jng.render()
    ms = (time.perf_counter() - t0) / n * 1000
    check(ms < 25, f"step+render {ms:.1f} ms/frame at {jng.gw}x{jng.gh}")

    print("13) temple theme: torch-lit flagstones")
    tmp = TempleShow(layout)
    check(tmp._base is not None and tmp._base.shape == (tmp.gh, tmp.gw, 3),
          "flagstone base texture built")
    check(len(tmp.glyphs) == CARVED_FLAGS, f"{len(tmp.glyphs)} carved flags")
    g0 = tmp.glyphs[0]
    for _ in range(300):  # 30 s standing right on the first carved flag
        tmp.set_tracks([{'id': 'w', 'x': g0['wx'] + 0.2, 'z': g0['wz']}])
        tmp.step(0.1)
    check(g0['glint'] > 0.3, f"carve glints on approach ({g0['glint']:.2f})")
    frame = tmp.render()
    check(frame.max() > 40, f"temple renders (max px {frame.max()})")
    lit2 = frame[tmp.mask > 0.9].astype(int)
    check(lit2[:, 0].mean() > lit2[:, 2].mean(), "the floor reads WARM (torchlight)")
    tex2 = tmp.hello_patches()
    ok2 = (all(len(base64.b64decode(t['rgba'])) == t['w'] * t['h'] * 4
               for t in [tex2['base'], tex2['island']] + tex2['glyphs'])
           and all(t.get('glow') for t in tex2['glyphs']))
    check(ok2, "textures exported (base + altar + glow carves)")

    print("14) temple: scarabs erupt, circle the feet, drain away")
    tmp2 = TempleShow(layout)
    tmp2._swarm['next'] = 1.0  # don't sit out the real gap
    seen_sc = {'scarab_erupt': False, 'scarab_drain': False}
    peak = 0
    for _ in range(450):  # 45 s, walker standing on the deck
        tmp2.set_tracks([{'id': 'w', 'x': 9.6, 'z': 1.0}])
        tmp2.step(0.1)
        st2 = tmp2.state()
        if st2['scarabs']:
            tmp2._heat_t = -1
            tmp2.render()  # exercise the sprite draw path mid-swarm
        peak = max(peak, len(st2['scarabs']))
        for e in st2['events']:
            if e['e'] in seen_sc:
                seen_sc[e['e']] = True
        if all(seen_sc.values()):
            break
    check(all(seen_sc.values()), f"erupt → drain both occurred ({seen_sc})")

    print("15) temple: the spider crawls slowly, scurries from feet")
    tmp3 = TempleShow(layout)
    tmp3.cue('test')
    sp = tmp3._spider
    x0s, z0s = sp['x'], sp['z']
    for _ in range(200):  # 20 s, nobody near
        tmp3.step(0.1)
    slow_d = math.hypot(sp['x'] - x0s, sp['z'] - z0s)
    check(tmp3._on_deck(sp['x'], sp['z']), "spider on the lit deck")
    check(slow_d < 2.5, f"crawl is slow ({slow_d:.2f} m in 20 s)")
    xs2, zs2 = sp['x'], sp['z']
    scurried = False
    for _ in range(40):  # 4 s with feet right on it
        tmp3.set_tracks([{'id': 'w', 'x': xs2, 'z': zs2}])
        tmp3.step(0.1)
        tmp3._heat_t = -1
        tmp3.render()  # exercise the sprite path mid-scurry
        scurried = scurried or any(
            e['e'] == 'spider_scurry' for e in tmp3.state()['events'])
    flee_d = math.hypot(sp['x'] - xs2, sp['z'] - zs2)
    check(scurried, "spider_scurry event fired")
    check(flee_d > 0.7, f"it got away ({flee_d:.2f} m)")
    check(peak >= 10, f"a proper swarm ({peak} scarabs at peak)")
    check(len(tmp2._swarm['scarabs']) == 0, "all scarabs gone after the drain")
    t0 = time.perf_counter()
    n = 200
    for _ in range(n):
        tmp.set_tracks([{'id': 'w', 'x': 10.0, 'z': 1.0}])
        tmp.step(1 / 30)
        tmp.render()
    ms = (time.perf_counter() - t0) / n * 1000
    check(ms < 25, f"step+render {ms:.1f} ms/frame at {tmp.gw}x{tmp.gh}")

    print("ALL PASS" if not FAIL else "FAILURES")
    sys.exit(FAIL)


if __name__ == '__main__':
    main()
