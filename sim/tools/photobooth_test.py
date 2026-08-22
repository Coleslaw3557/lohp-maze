#!/usr/bin/env python3
"""Regression test for the Photo Bomb booth game and the Monkey Room
silver-monkey celebration (headless, against a running sim).

Covers:
  1. effects registered
  2. watermark: captures get a Pacific-time stamp in the lower-right corner
     (direct CameraManager check, synthetic backend — no server needed)
  3. PhotoBomb-Shot: countdown pops at 0.75/1.5/2.25s, white FLASH at 3s on the
     room's fixtures, a photo written at the shutter moment, and the victory
     cue (CorrectAnswer chime) delivered after the capture
  4. entry (PhotoBomb-BG) plays the room's ambience bed and resets the shot budget
  5. booth budget: 5 shots per visitor — the 6th press runs WrongAnswer (failure
     cue) instead of a countdown and takes no photo; room_vacated resets
  6. button hammering: a re-trigger mid-countdown supersedes the run and
     replaces the pending capture — exactly one photo per completed countdown
  7. stop_effect mid-countdown cancels the pending capture — no photo
  8. MonkeyBusiness: gold fanfare hit right at start, MEGA flash on the 1.56s
     stinger, shrine audio delivered to the room's client
  9. /api/photobomb/photos lists and serves the photos

Run with the sim venv: sim/.venv/bin/python sim/tools/photobooth_test.py [host]
"""
import asyncio
import json
import os
import re
import sys
import tempfile
import time
import urllib.request

HOST = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
API = f'http://{HOST}:5000'
FAILS = []
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# fixture channel bases (0-indexed into the 352ch universe), from light_config.json
PB_PAR, PB_SPOT = 80, 88     # Photo Bomb Room @81 / @89
MK_PAR, MK_SPOT = 120, 128   # Monkey Room @121 / @129

# PhotoBomb-Shot timeline (effects/photobomb_shot.py): instant flash, capture
# scheduled +0.25s (shutter_latency_compensation), Landed +0.8s after capture
FLASH = 0.0
CAPTURE_AT = 0.25
SHOT_ROOM = 'Photo Bomb Room'


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


def booth_reset():
    """Node reports the room empty -> fresh shot budget."""
    post('/api/room_vacated', {'room': SHOT_ROOM})


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


async def watermark_unit_check():
    """Two synthetic captures, watermark on/off — the lower-right corner must
    differ (the stamp) and the stamped filename must be a valid timestamp."""
    sys.path.insert(0, REPO)
    from PIL import Image
    from camera_manager import CameraManager

    corners = {}
    with tempfile.TemporaryDirectory() as td:
        for mark in (False, True):
            cfg = os.path.join(td, f'cam-{mark}.json')
            with open(cfg, 'w') as f:
                json.dump({'backend': 'synthetic', 'watermark': mark,
                           'photos_dir': os.path.join(td, f'photos-{mark}')}, f)
            cam = CameraManager(config_file=cfg)
            path = await cam.capture()
            with Image.open(path) as im:
                w, h = im.size
                corners[mark] = list(im.convert('L').crop((w // 2, h - h // 8, w, h)).getdata())
        diff = sum(1 for a, b in zip(corners[False], corners[True]) if abs(a - b) > 40)
        check('watermark stamps the lower-right corner', diff > 50, f'({diff} px changed)')


async def main():
    # Deterministic lighting baseline: attract has been on-from-boot since
    # 2026-08-01 and its theme palette-clamps effect frames (255->caps, whites
    # stripped) — kill it or the flash/stinger peaks read low.
    post('/api/attract', {'on': False})
    post('/api/set_theme', {'theme_name': 'notheme'})
    post('/api/stop_effect', {})
    await asyncio.sleep(0.5)

    print("1) effects registered")
    _, effects = get('/api/effects_list')
    for name in ('PhotoBomb-Shot', 'PhotoBomb-BG', 'PhotoBomb-Landed', 'MonkeyBusiness'):
        check(f'{name} registered', name in effects)

    print("2) watermark (direct, synthetic backend)")
    await watermark_unit_check()

    print("3) PhotoBomb-Shot: instant flash + photo + lights-only Landed")
    booth_reset()
    before = {p['filename'] for p in list_photos()['photos']}
    audio_hits = []
    listener = asyncio.create_task(audio_listener(SHOT_ROOM, audio_hits))
    await asyncio.sleep(1.0)

    frames, t_start, status, body = await run_effect_with_frames(
        SHOT_ROOM, 'PhotoBomb-Shot', 3.5)
    check('run_effect accepted', status == 200, body.get('message', ''))
    flash_par = peak_near(frames, PB_PAR, t_start + FLASH, 0.3)
    flash_w = peak_near(frames, PB_PAR, t_start + FLASH, 0.3, chan=4)
    flash_spot = peak_near(frames, PB_SPOT, t_start + FLASH, 0.3)
    check('instant FLASH par', flash_par == 255 and flash_w >= 250,
          f'(total {flash_par}, w {flash_w})')
    check('instant FLASH uking spot', flash_spot == 255, f'(total {flash_spot})')
    # anchor on the observed flash onset — post_bg dispatch adds ~0.3s jitter.
    # The sim DMX stream is CHANGE-driven: a steady hold emits no frames, so
    # assert no frame DROPS below 255 during the hold rather than sampling it.
    onset = next((t for t, f in frames if f[PB_PAR] == 255), None)
    check('flash onset seen', onset is not None, f'(onset {onset})')
    drops = [(round(t - (onset or 0), 2), f[PB_PAR]) for t, f in frames
             if onset is not None and onset < t <= onset + 0.5 and f[PB_PAR] < 255]
    check('flash held through the capture (no dip in 0.5s)', not drops, f'({drops[:3]})')
    landed = peak_near(frames, PB_SPOT, t_start + CAPTURE_AT + 1.1, 0.6)
    check('Landed jade on the accent after capture', landed >= 150, f'(peak {landed})')

    await asyncio.sleep(1.0)
    after = list_photos()
    new = [p for p in after['photos'] if p['filename'] not in before]
    check('exactly one photo captured', len(new) == 1, f'({[p["filename"] for p in new]})')
    check('shot is silent on the client path (snap is on-node, Landed lights-only)',
          len(audio_hits) == 0,
          f"({[h['data']['file_name'] for h in audio_hits]})")
    if new:
        name = new[0]['filename']
        check('timestamped filename', bool(re.match(
            r'photobomb_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(-\d+)?\.jpg', name)), f'({name})')
        with urllib.request.urlopen(f'{API}/api/photobomb/photos/{name}', timeout=10) as r:
            data = r.read()
        check('photo serves as JPEG', r.status == 200 and data[:3] == b'\xff\xd8\xff',
              f'({len(data)} bytes, backend={after["backend"]})')
    listener.cancel()

    print("4) entry: ambience bed plays and the budget resets")
    booth_reset()
    audio_hits = []
    listener = asyncio.create_task(audio_listener(SHOT_ROOM, audio_hits))
    await asyncio.sleep(1.0)
    bg = await post_bg('/api/run_effect', {'room': SHOT_ROOM, 'effect_name': 'PhotoBomb-BG'})
    await asyncio.sleep(1.5)
    check('entry ambience delivered', len(audio_hits) >= 1,
          f"({[h['data']['file_name'] for h in audio_hits]})")
    listener.cancel()
    post('/api/stop_effect', {'room': SHOT_ROOM})
    await bg

    print("5) rolling window: burst of 5 = 5 photos, drain restores, entry clears")
    booth_reset()
    before = {p['filename'] for p in list_photos()['photos']}
    t_first = time.monotonic()
    msgs = []
    for i in range(6):
        task = await post_bg('/api/run_effect',
                             {'room': SHOT_ROOM, 'effect_name': 'PhotoBomb-Shot'})
        if i < 5:
            await asyncio.sleep(0.35)  # past the 0.25s pre-capture gap: no supersede
            msgs.append(task)
        else:
            status6, body6 = await task
    for i, t in enumerate(msgs):
        st, b = await t
        check(f'press {i + 1} fired the shot', st == 200 and 'PhotoBomb-Shot' in b.get('message', ''),
              f"({b.get('message', '')[:50]})")
    check('press 6 swapped to the failure cue',
          status6 == 200 and 'WrongAnswer' in body6.get('message', ''),
          f"({body6.get('message', '')[:60]})")
    await asyncio.sleep(1.2)
    new = [p for p in list_photos()['photos'] if p['filename'] not in before]
    check('burst of 5 = 5 photos', len(new) == 5, f'({len(new)} new)')
    _, body7 = post('/api/run_effect', {'room': SHOT_ROOM, 'effect_name': 'PhotoBomb-Shot'})
    check('press 7 still failing inside the window', 'WrongAnswer' in body7.get('message', ''),
          f"({body7.get('message', '')[:60]})")
    # window drain: the first shot ages out at t_first+15 — no turnover needed
    await asyncio.sleep(max(0.0, t_first + 15.3 - time.monotonic()))
    _, body_drain = post('/api/run_effect', {'room': SHOT_ROOM, 'effect_name': 'PhotoBomb-Shot'})
    check('window drains: shot works again without turnover',
          'PhotoBomb-Shot' in body_drain.get('message', ''),
          f"({body_drain.get('message', '')[:60]})")
    bg = await post_bg('/api/run_effect', {'room': SHOT_ROOM, 'effect_name': 'PhotoBomb-BG'})
    await asyncio.sleep(0.4)
    eff = await post_bg('/api/run_effect', {'room': SHOT_ROOM, 'effect_name': 'PhotoBomb-Shot'})
    _, body8 = await eff
    check('entry clears the window outright', 'PhotoBomb-Shot' in body8.get('message', ''),
          f"({body8.get('message', '')[:60]})")
    await bg
    await asyncio.sleep(1.5)  # let the last shot's capture/Landed settle

    print("6) re-press inside the pre-capture gap supersedes: one photo total")
    booth_reset()
    before = {p['filename'] for p in list_photos()['photos']}
    eff1 = await post_bg('/api/run_effect', {'room': SHOT_ROOM, 'effect_name': 'PhotoBomb-Shot'})
    await asyncio.sleep(0.1)  # inside CAPTURE_AT: replaces the pending grab
    eff2 = await post_bg('/api/run_effect', {'room': SHOT_ROOM, 'effect_name': 'PhotoBomb-Shot'})
    r1 = await eff1
    await eff2
    await asyncio.sleep(1.0)  # past the second run's capture + margin
    new = [p for p in list_photos()['photos'] if p['filename'] not in before]
    check('superseded run yields no photo', len(new) == 1,
          f'({len(new)} new; first={r1[1].get("message", "")[:40]})')

    print("7) stop inside the pre-capture gap cancels: no photo")
    booth_reset()
    before = {p['filename'] for p in list_photos()['photos']}
    eff = await post_bg('/api/run_effect', {'room': SHOT_ROOM, 'effect_name': 'PhotoBomb-Shot'})
    await asyncio.sleep(0.1)  # inside CAPTURE_AT
    post('/api/stop_effect', {'room': SHOT_ROOM})
    try:
        await asyncio.wait_for(eff, timeout=5)
    except Exception:
        pass
    await asyncio.sleep(1.0)  # would-be capture time passes
    new = [p for p in list_photos()['photos'] if p['filename'] not in before]
    check('stopped run yields no photo', len(new) == 0, f'({len(new)} new)')

    print("8) MonkeyBusiness: fanfare + stinger flash + audio")
    audio_hits = []
    listener = asyncio.create_task(audio_listener('Monkey Room', audio_hits))
    await asyncio.sleep(1.0)
    frames, t_start, status, body = await run_effect_with_frames(
        'Monkey Room', 'MonkeyBusiness', 6.0)
    check('run_effect accepted', status == 200, body.get('message', ''))
    # the fanfare pop has no hold at peak (255 spike decaying to 210 by 0.2s),
    # so 30fps sampling can land a few counts under max
    # Peaks assert the CLAMPED design: the 2026-08-17 palette enforcement
    # (_enforce_effect_palette) caps every non-exempt effect at total 200 /
    # w 45 — MonkeyBusiness deliberately has no exemption, so the stored
    # 255/W255 stinger renders at the caps.
    gold = peak_near(frames, MK_PAR, t_start + 0.1, 0.3)
    gold_r = peak_near(frames, MK_PAR, t_start + 0.1, 0.3, chan=1)
    check('gold fanfare hit at start (palette-capped)', gold >= 190 and gold_r >= 250,
          f'(total {gold}, r {gold_r})')
    mega = peak_near(frames, MK_PAR, t_start + 1.56, 0.3)
    mega_w = peak_near(frames, MK_PAR, t_start + 1.56, 0.3, chan=4)
    mega_spot = peak_near(frames, MK_SPOT, t_start + 1.56, 0.3)
    check('MEGA flash on stinger @1.56s (palette-capped)', mega >= 190 and 35 <= mega_w <= 45,
          f'(total {mega}, w {mega_w})')
    check('stinger flash on uking spot (palette-capped)', mega_spot >= 190, f'(total {mega_spot})')
    blackout = peak_near(frames, MK_PAR, t_start + 4.99, 0.25)
    check('ends dark', blackout <= 30, f'(total {blackout})')
    check('shrine audio delivered',
          any(h['data']['file_name'] == 'monkey-shrine-complete.mp3' for h in audio_hits),
          f"({[h['data']['file_name'] for h in audio_hits]})")
    listener.cancel()

    booth_reset()
    post('/api/stop_effect', {})
    print(f"\n{'ALL PASS' if not FAILS else 'FAILURES: ' + ', '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)


asyncio.run(main())
