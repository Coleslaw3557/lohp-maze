#!/usr/bin/env python3
"""Regression test for the Photo Bomb camera sequence and the Monkey Room
silver-monkey celebration (headless, against a running sim).

Covers:
  1. both effects registered
  2. PhotoBomb-Shot: countdown pops at 1/2/3s, white FLASH at 4s on the room's
     fixtures, countdown audio delivered to the room's audio client, and a
     timestamped photo written at the shutter moment
  3. button hammering: a re-trigger mid-countdown supersedes the run and
     replaces the pending capture — exactly one photo per completed countdown
  4. stop_effect mid-countdown cancels the pending capture — no photo
  5. MonkeyBusiness: gold fanfare hit right at start, MEGA flash on the 1.56s
     stinger, shrine audio delivered to the room's client
  6. /api/photobomb/photos lists and serves the photos

Run with the sim venv: sim/.venv/bin/python sim/tools/photobooth_test.py [host]
"""
import asyncio
import json
import re
import sys
import time
import urllib.request

HOST = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
API = f'http://{HOST}:5000'
FAILS = []

# fixture channel bases (0-indexed into the 352ch universe), from light_config.json
PB_PAR, PB_SPOT = 80, 88     # Photo Bomb Room @81 / @89
MK_PAR, MK_SPOT = 120, 128   # Monkey Room @121 / @129


def check(name, ok, detail=''):
    print(f"  {'PASS' if ok else 'FAIL'}  {name} {detail}")
    if not ok:
        FAILS.append(name)


def get(path, timeout=10):
    with urllib.request.urlopen(API + path, timeout=timeout) as r:
        return r.status, json.loads(r.read())


def post(path, data, timeout=30):
    req = urllib.request.Request(API + path, data=json.dumps(data).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read())


async def post_bg(path, data):
    return asyncio.create_task(asyncio.to_thread(post, path, data))


async def collect_timed_frames(seconds, out, t0):
    """Append (t_since_t0, bytes(frame)) tuples for `seconds`."""
    import websockets
    async with websockets.connect(f'ws://{HOST}:5001/sim/dmx') as ws:
        try:
            async with asyncio.timeout(seconds):
                while True:
                    msg = json.loads(await ws.recv())
                    out.append((time.monotonic() - t0, bytes(msg['ch'])))
        except TimeoutError:
            pass


def peak_near(frames, base, t_expect, window=0.35, chan=0):
    """Max value of fixture channel base+chan within t_expect±window."""
    vals = [f[base + chan] for t, f in frames if abs(t - t_expect) <= window]
    return max(vals) if vals else 0


def list_photos():
    _, body = get('/api/photobomb/photos')
    return body


async def run_effect_with_frames(room, effect, record_s):
    """Start collecting frames, fire the effect, return (frames, post_result)."""
    frames = []
    t0 = time.monotonic()
    collector = asyncio.create_task(collect_timed_frames(record_s, frames, t0))
    await asyncio.sleep(0.25)  # collector connected; effect start ≈ t0+0.25
    eff = await post_bg('/api/run_effect', {'room': room, 'effect_name': effect})
    await collector
    status, body = await eff
    return frames, 0.25, status, body


async def audio_listener(room, hits):
    import websockets
    async with websockets.connect(f'ws://{HOST}:8765') as ws:
        await ws.send(json.dumps({
            'type': 'client_connected',
            'data': {'unit_name': 'PHOTOBOOTH-TEST', 'associated_rooms': [room]},
        }))
        while True:
            msg = json.loads(await ws.recv())
            if msg.get('type') == 'play_effect_audio':
                hits.append(msg)


async def main():
    post('/api/set_theme', {'theme_name': 'notheme'})
    post('/api/stop_effect', {})
    await asyncio.sleep(0.5)

    print("1) effects registered")
    _, effects = get('/api/effects_list')
    check('PhotoBomb-Shot registered', 'PhotoBomb-Shot' in effects)
    check('MonkeyBusiness registered', 'MonkeyBusiness' in effects)

    print("2) PhotoBomb-Shot: lights timeline + audio + photo")
    before = {p['filename'] for p in list_photos()['photos']}
    audio_hits = []
    listener = asyncio.create_task(audio_listener('Photo Bomb Room', audio_hits))
    await asyncio.sleep(1.0)

    frames, t_start, status, body = await run_effect_with_frames(
        'Photo Bomb Room', 'PhotoBomb-Shot', 8.0)
    check('run_effect accepted', status == 200, body.get('message', ''))
    # countdown pops on both fixtures at 1/2/3s after effect start
    for beep in (1.0, 2.0, 3.0):
        pk = peak_near(frames, PB_PAR, t_start + beep)
        check(f'countdown pop @{beep:.0f}s', pk >= 200, f'(par total_dim peak {pk})')
    flash_par = peak_near(frames, PB_PAR, t_start + 4.0, 0.3)
    flash_w = peak_near(frames, PB_PAR, t_start + 4.0, 0.3, chan=4)
    flash_spot = peak_near(frames, PB_SPOT, t_start + 4.0, 0.3)
    check('FLASH @4s par', flash_par == 255 and flash_w >= 250, f'(total {flash_par}, w {flash_w})')
    check('FLASH @4s uking spot', flash_spot == 255, f'(total {flash_spot})')
    dip = peak_near(frames, PB_PAR, t_start + 3.85, 0.08)
    check('anticipation dip before flash', dip < 100, f'(total {dip})')

    check('countdown audio delivered',
          any(h['data']['file_name'] == 'photobomb-countdown.mp3' for h in audio_hits),
          f"({[h['data']['file_name'] for h in audio_hits]})")

    after = list_photos()
    new = [p for p in after['photos'] if p['filename'] not in before]
    check('exactly one photo captured', len(new) == 1, f'({[p["filename"] for p in new]})')
    if new:
        name = new[0]['filename']
        check('timestamped filename', bool(re.match(r'photobomb_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(-\d+)?\.jpg', name)), f'({name})')
        with urllib.request.urlopen(f'{API}/api/photobomb/photos/{name}', timeout=10) as r:
            data = r.read()
        check('photo serves as JPEG', r.status == 200 and data[:3] == b'\xff\xd8\xff',
              f'({len(data)} bytes, backend={after["backend"]})')
    listener.cancel()

    print("3) re-press mid-countdown supersedes: one photo total")
    before = {p['filename'] for p in list_photos()['photos']}
    eff1 = await post_bg('/api/run_effect', {'room': 'Photo Bomb Room', 'effect_name': 'PhotoBomb-Shot'})
    await asyncio.sleep(1.5)
    eff2 = await post_bg('/api/run_effect', {'room': 'Photo Bomb Room', 'effect_name': 'PhotoBomb-Shot'})
    r1 = await eff1
    r2 = await eff2
    await asyncio.sleep(1.0)  # past the second run's capture + margin
    new = [p for p in list_photos()['photos'] if p['filename'] not in before]
    check('superseded run yields no photo', len(new) == 1,
          f'({len(new)} new; first={r1[1].get("message", "")[:40]})')

    print("4) stop mid-countdown cancels the capture: no photo")
    before = {p['filename'] for p in list_photos()['photos']}
    eff = await post_bg('/api/run_effect', {'room': 'Photo Bomb Room', 'effect_name': 'PhotoBomb-Shot'})
    await asyncio.sleep(1.5)
    post('/api/stop_effect', {'room': 'Photo Bomb Room'})
    try:
        await asyncio.wait_for(eff, timeout=5)
    except Exception:
        pass
    await asyncio.sleep(3.5)  # would-be shutter time passes
    new = [p for p in list_photos()['photos'] if p['filename'] not in before]
    check('stopped run yields no photo', len(new) == 0, f'({len(new)} new)')

    print("5) MonkeyBusiness: fanfare + stinger flash + audio")
    audio_hits = []
    listener = asyncio.create_task(audio_listener('Monkey Room', audio_hits))
    await asyncio.sleep(1.0)
    frames, t_start, status, body = await run_effect_with_frames(
        'Monkey Room', 'MonkeyBusiness', 6.0)
    check('run_effect accepted', status == 200, body.get('message', ''))
    # the fanfare pop has no hold at peak (255 spike decaying to 210 by 0.2s),
    # so 30fps sampling can land a few counts under max
    gold = peak_near(frames, MK_PAR, t_start + 0.1, 0.3)
    gold_r = peak_near(frames, MK_PAR, t_start + 0.1, 0.3, chan=1)
    check('gold fanfare hit at start', gold >= 235 and gold_r >= 250, f'(total {gold}, r {gold_r})')
    mega = peak_near(frames, MK_PAR, t_start + 1.56, 0.3)
    mega_w = peak_near(frames, MK_PAR, t_start + 1.56, 0.3, chan=4)
    mega_spot = peak_near(frames, MK_SPOT, t_start + 1.56, 0.3)
    # w ramps 255->200 over 180ms after the hit; a 30fps frame can sample a
    # few counts below peak, so require "near max" not exactly max
    check('MEGA flash on stinger @1.56s', mega == 255 and mega_w >= 240, f'(total {mega}, w {mega_w})')
    check('stinger flash on uking spot', mega_spot == 255, f'(total {mega_spot})')
    blackout = peak_near(frames, MK_PAR, t_start + 4.99, 0.25)
    check('ends dark', blackout <= 30, f'(total {blackout})')
    check('shrine audio delivered',
          any(h['data']['file_name'] == 'monkey-shrine-complete.mp3' for h in audio_hits),
          f"({[h['data']['file_name'] for h in audio_hits]})")
    listener.cancel()

    post('/api/stop_effect', {})
    print(f"\n{'ALL PASS' if not FAILS else 'FAILURES: ' + ', '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)


asyncio.run(main())
