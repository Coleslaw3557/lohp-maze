#!/usr/bin/env python3
"""End-to-end smoke test for the simulator (headless).

Exercises the same contracts the browser sim and real hardware use:
  1. /sim/dmx WS feed delivers universe frames
  2. a virtual sensor POST (/api/run_effect) visibly changes DMX frames
  3. a theme keeps frames changing continuously
  4. an audio client speaking the unit WS protocol receives play_effect_audio

Note: the server holds /api/run_effect open until the effect finishes (the
real Pi triggers use a 30s timeout for the same reason), so effect POSTs run
in a thread concurrently with frame collection.

Run with the sim venv: sim/.venv/bin/python sim/tools/smoke_test.py [host]
"""
import asyncio
import json
import sys
import urllib.request

HOST = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
API = f'http://{HOST}:5000'
FAILS = []


def check(name, ok, detail=''):
    print(f"  {'PASS' if ok else 'FAIL'}  {name} {detail}")
    if not ok:
        FAILS.append(name)


def post(path, data, timeout=30):
    req = urllib.request.Request(API + path, data=json.dumps(data).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read())


async def post_bg(path, data):
    """Fire a POST without blocking the loop; server holds it for the effect duration."""
    return asyncio.create_task(asyncio.to_thread(post, path, data))


async def collect_frames(seconds, out):
    import websockets
    async with websockets.connect(f'ws://{HOST}:5001/sim/dmx') as ws:
        try:
            async with asyncio.timeout(seconds):
                while True:
                    msg = json.loads(await ws.recv())
                    out.append(bytes(msg['ch']))
        except TimeoutError:
            pass


async def main():
    import websockets

    print("1) DMX frame feed")
    frames = []
    await collect_frames(2, frames)
    check('frames received', len(frames) >= 1, f'({len(frames)} in 2s)')

    print("2) trigger contract -> DMX change (Lightning in Entrance, fixture @1)")
    frames = []
    collector = asyncio.create_task(collect_frames(3.0, frames))
    await asyncio.sleep(0.3)
    eff = await post_bg('/api/run_effect', {'room': 'Entrance', 'effect_name': 'Lightning'})
    await collector
    status, body = await eff
    check('run_effect accepted', status == 200, body.get('message', ''))
    ch1_values = {f[0] for f in frames}  # fixture @1 channel 1 (total_dimming)
    check('fixture @1 responds', len(ch1_values) > 1, f'({len(ch1_values)} distinct values on ch1)')

    print("3) theme engine -> continuous frames")
    status, body = post('/api/set_theme', {'theme_name': 'NeonNightlife'})
    check('set_theme accepted', status == 200, body.get('message', ''))
    frames = []
    await collect_frames(2, frames)
    check('theme animates universe', len(frames) >= 8 and len({bytes(f) for f in frames}) >= 4,
          f'({len(frames)} frames, {len({bytes(f) for f in frames})} distinct)')

    print("4) audio unit protocol")
    got_audio = asyncio.Event()
    audio_msg = {}

    async def audio_client():
        async with websockets.connect(f'ws://{HOST}:8765') as ws:
            await ws.send(json.dumps({
                'type': 'client_connected',
                'data': {'unit_name': 'SMOKE-TEST', 'associated_rooms': ['Entrance']},
            }))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get('type') == 'play_effect_audio':
                    audio_msg.update(msg)
                    got_audio.set()
                    return

    task = asyncio.create_task(audio_client())
    await asyncio.sleep(1.0)  # let the room claim register
    eff = await post_bg('/api/run_effect', {'room': 'Entrance', 'effect_name': 'Entrance'})
    try:
        await asyncio.wait_for(got_audio.wait(), timeout=8)
        d = audio_msg.get('data', {})
        check('play_effect_audio received', True,
              f"(room={audio_msg.get('room')}, file={d.get('file_name')}, vol={d.get('volume')})")
        audio_file = d.get('file_name')
        if audio_file:
            with urllib.request.urlopen(f'{API}/api/audio/{audio_file}', timeout=10) as r:
                check('audio file downloadable', r.status == 200, f'({len(r.read())} bytes)')
    except asyncio.TimeoutError:
        check('play_effect_audio received', False, '(timeout)')
    finally:
        task.cancel()
        try:
            await eff  # let the held run_effect finish so cleanup posts don't queue oddly
        except Exception:
            pass

    post('/api/set_theme', {'theme_name': 'notheme'})
    post('/api/stop_effect', {})

    print(f"\n{'ALL PASS' if not FAILS else 'FAILURES: ' + ', '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)


asyncio.run(main())
