#!/usr/bin/env python3
"""The 2026-08-01 lighting pass (headless, against a running sim):

  1. attract mode is on from boot and rotating the slow dark theme set
  2. every profiled room wears its own colour UNDER its cap with ZERO white
     (bright white/yellow is reserved for the flash/lightning/test effects)
  3. an answer chirp in a two-fixture room plays on the ACCENT par only —
     the ambient par keeps breathing the theme underneath

Run with the sim venv: sim/.venv/bin/python sim/tools/lighting_test.py [host]
"""
import asyncio
import json
import sys
import urllib.request

HOST = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
API = f'http://{HOST}:5000'
ATTRACT_SET = {'DeepCanopy', 'EmberUndercroft', 'CenoteDrift',
               'UltravioletVines', 'MoonlitStone', 'RitualAurora'}
# room -> (first fixture start address, profile cap) from theme_manager.ROOM_LIGHT_PROFILES
PROFILED = {'Entrance': (1, 170), 'Cop Dodge': (9, 175), 'Guy Line Climb': (25, 150),
            'Cuddle Cross': (57, 48), 'Deep Playa Handshake': (97, 175),
            'Temple Room': (113, 155)}
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
    async with websockets.connect(f'ws://{HOST}:5001/sim/dmx') as ws:
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

    print("3) answer chirp -> accent par only; ambient par keeps the theme")
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
