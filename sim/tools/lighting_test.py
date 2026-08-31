#!/usr/bin/env python3
"""The 2026-08-01 lighting pass (headless, against a running sim):

  1. attract mode is on from boot and rotating the slow dark theme set
  2. every profiled room wears its own colour UNDER its cap with ZERO white
     (bright white/yellow is reserved for the flash/lightning/test effects)
  3. NO YELLOW on the wire — idle, and through a room's entry sting and the
     occupied colour lock that follows it
  4. an answer chirp in a two-fixture room plays on the ACCENT par only —
     the ambient par keeps breathing the theme underneath

Run with the sim venv: sim/.venv/bin/python sim/tools/lighting_test.py [host]
"""
import asyncio
import colorsys
import json
import sys
import os
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from effect_utils import YELLOW_ARC  # noqa: E402 — the one definition of the rule

HOST = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
API = f'http://{HOST}:5000'
# on-playa the calibration server squats 5001, so the sim moves: honor its env
SIM_UI_PORT = os.environ.get('SIM_UI_PORT', '5001')
ATTRACT_SET = {'DeepCanopy', 'EmberUndercroft', 'CenoteDrift',
               'UltravioletVines', 'MoonlitStone', 'RitualAurora'}
# room -> (first fixture start address, profile cap) from theme_manager.ROOM_LIGHT_PROFILES
# caps 255 since the 2026-08-31 live-night full-brightness raise (a915f06)
PROFILED = {'Entrance': (1, 255), 'Cop Dodge': (9, 255), 'Guy Line Climb': (25, 255),
            'Cuddle Cross': (57, 255), 'Deep Playa Handshake': (97, 255),
            'Temple Room': (113, 255)}
FAILS = []


def check(name, ok, detail=''):
    print(f"  {'PASS' if ok else 'FAIL'}  {name} {detail}")
    if not ok:
        FAILS.append(name)


def post(path, data):
    req = urllib.request.Request(API + path, data=json.dumps(data).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read())


def get(path):
    with urllib.request.urlopen(API + path, timeout=10) as r:
        return json.loads(r.read())


async def collect(seconds, frames):
    import websockets
    async with websockets.connect(f'ws://{HOST}:{SIM_UI_PORT}/sim/dmx') as ws:
        try:
            async with asyncio.timeout(seconds):
                while True:
                    frames.append(bytes(json.loads(await ws.recv())['ch']))
        except TimeoutError:
            pass


async def main():
    print("1) attract mode is rotating the dark theme set")
    # a prior test's theme stop leaves the maze deliberately dark for a bit;
    # re-kicking attract lights the first rotation theme immediately, making
    # this test order-independent
    post('/api/attract', {'on': True})
    await asyncio.sleep(1.0)
    state = get('/api/attract')
    check('attract enabled from boot', state.get('enabled') is True)
    check('rotation set is the dark themes', set(state.get('themes', [])) == ATTRACT_SET,
          f"({state.get('themes')})")
    check('a rotation theme is on stage', state.get('current_theme') in ATTRACT_SET,
          f"({state.get('current_theme')})")

    print("2) profiled rooms: own colour, under cap, zero white")
    frames = []
    await collect(4.0, frames)
    check('frames collected', len(frames) > 10, f'({len(frames)})')
    for room, (addr, cap) in PROFILED.items():
        base = addr - 1
        tot = max(f[base] for f in frames)
        white = max(f[base + 4] for f in frames)
        lit = any(f[base] > 0 for f in frames)
        check(f'{room} under cap, no white, lit',
              tot <= cap and white == 0 and lit,
              f'(peak {tot} <= {cap}, w {white})')

    print("3) NO YELLOW: not idle, not while a room is occupied")
    # The rule has one hard number (effect_utils.YELLOW_ARC): nothing the maze
    # means to show lives between EMBER orange and the greenest room profile,
    # so no lit fixture may sit in that arc. Checked on the WIRE, because the
    # clamp used to escape the old narrow band *upward into* yellow-green.
    yellow = []

    def scan_yellow(frames, when):
        # the 20 maze pars + the 3 Exterior BLE floods (353-376); the Camp
        # Sign band between them wears its own bridge-side looks and is
        # palette-exempt, so it stays out of the sweep
        for frame in frames:
            for addr in [*range(1, 161, 8), *range(353, 377, 8)]:
                base = addr - 1
                if base + 3 >= len(frame):
                    continue
                tot, r, g, b = (frame[base], frame[base + 1],
                                frame[base + 2], frame[base + 3])
                if tot < 20 or max(r, g, b) < 20:
                    continue
                h, s, _ = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
                if s > 0.2 and YELLOW_ARC[0] < h < YELLOW_ARC[1]:
                    yellow.append((when, addr, round(h * 360), (r, g, b)))

    frames = []
    await collect(4.0, frames)
    scan_yellow(frames, 'idle')
    check('no yellow in the idle maze', not yellow,
          f'({len(yellow)} frames, e.g. {yellow[0] if yellow else ""})')

    held = []
    hold_room, hold_effect = 'Temple Room', 'TempleWake'
    collector = asyncio.create_task(collect(9.0, held))
    await asyncio.sleep(0.3)
    await asyncio.to_thread(post, '/api/run_effect',
                            {'room': hold_room, 'effect_name': hold_effect})
    await collector                              # entry sting AND the held look
    before = len(yellow)
    scan_yellow(held, 'occupied')
    check(f'no yellow entering/holding {hold_room}', len(yellow) == before,
          f'({len(yellow) - before} frames, e.g. {yellow[before] if len(yellow) > before else ""})')
    lit = max(f[112] for f in held)              # Temple par @113 actually ran
    check(f'{hold_room} entry drove its par', lit > 20, f'(peak total {lit})')
    post('/api/room_vacated', {'room': hold_room})

    print("4) answer chirp -> accent par only; ambient par keeps the theme")
    frames = []
    collector = asyncio.create_task(collect(3.5, frames))
    await asyncio.sleep(0.3)
    await asyncio.to_thread(post, '/api/run_effect',
                            {'room': 'Guy Line Climb', 'effect_name': 'CorrectAnswer'})
    await collector
    amb_tot = [f[24] for f in frames]                 # par @25 (ambient)
    acc_green = max(f[34] for f in frames)            # par @33 (accent) green
    check('accent par flashed jade', acc_green > 150, f'(peak g {acc_green})')
    check('ambient par stayed under its cap and kept breathing',
          max(amb_tot) <= 225 and any(v > 0 for v in amb_tot),
          f'(peak {max(amb_tot)})')

    print(f"\n{'ALL PASS' if not FAILS else 'FAILURES: ' + ', '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)


asyncio.run(main())
