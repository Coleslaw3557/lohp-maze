#!/usr/bin/env python3
"""Ambient one-shots + global maze ambience (headless).

Exercises maze_ambient_manager.py and the global maze ambience bed:

  1. GET /api/ambient reports the armed timers from audio_config
     `ambient_oneshots` (maze pool + the Entrance room pool)
  2. room_backgrounds is intentionally empty; ambience is global except Cuddle
  3. a client covering Entrance/Gate receives the global maze ambience bed
  4. POST /api/ambient {"room": "Entrance"} lands one hallow/lightson
     one-shot in Entrance, over the global bed, without stopping it
  5. POST /api/ambient {"maze": true} lands a MazeAmbient file in some
     room that can play audio; within a few firings one lands on this
     test's rooms and the file is from the crow/dog/owl/... pool
  6. bad audition requests 400 instead of firing

Run with the sim venv: sim/.venv/bin/python sim/tools/ambient_test.py [host]
"""
import asyncio
import json
import os
import sys
import urllib.error
import urllib.request

HOST = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
API = f'http://{HOST}:5000'
SPY_ROOMS = ['Entrance', 'Gate']
ENTRANCE_POOL = {f'hallow0{i}.wav' for i in range(1, 9)} | {'lightson.wav'}
MAZE_PREFIXES = ('crow', 'dog', 'forest_bird', 'desert_', 'owl',
                 'wolf_howl', 'rain', 'wind_gust')
GLOBAL_BED_BASENAMES = {
    *(f'The 7th Continent Soundscape - Area {roman}.mp3'
      for roman in ('I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X')),
    'rainstorm.mp3',
    'hallowloop.wav',
    'forest_cliff.wav',
    'forest_high_wind.wav',
    'forest_life.wav',
}
FAILS = []


def check(name, ok, detail=''):
    print(f"  {'PASS' if ok else 'FAIL'}  {name} {detail}")
    if not ok:
        FAILS.append(name)


def post(path, data, timeout=30):
    req = urllib.request.Request(API + path, data=json.dumps(data).encode(),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


def get(path, timeout=10):
    with urllib.request.urlopen(API + path, timeout=timeout) as r:
        return r.status, json.loads(r.read())


class AudioSpy:
    """The unit WS protocol, recording what our rooms are told to play."""

    def __init__(self, rooms):
        self.rooms = rooms
        self.msgs = []
        self._task = None

    async def __aenter__(self):
        import websockets
        self.ws = await websockets.connect(f'ws://{HOST}:8765')
        await self.ws.send(json.dumps({
            'type': 'client_connected',
            'data': {'unit_name': 'AMBIENT-TEST', 'associated_rooms': self.rooms},
        }))
        self._task = asyncio.create_task(self._pump())
        await asyncio.sleep(1.0)  # let the room claim register
        return self

    async def _pump(self):
        while True:
            msg = json.loads(await self.ws.recv())
            self.msgs.append(msg)

    async def __aexit__(self, *exc):
        self._task.cancel()
        await self.ws.close()

    def take(self, *types):
        got = [m for m in self.msgs if m.get('type') in types]
        self.msgs[:] = [m for m in self.msgs if m.get('type') not in types]
        return got


async def main():
    print("1) armed timers")
    status, state = get('/api/ambient')
    maze = state.get('maze') or {}
    rooms = state.get('rooms') or {}
    check('GET /api/ambient', status == 200)
    check('maze pool armed', maze.get('effect') == 'MazeAmbient',
          f"({maze})")
    check('Entrance room pool armed',
          (rooms.get('Entrance') or {}).get('effect') == 'Entrance-Ambient',
          f"({sorted(rooms)})")

    print("2) room_backgrounds intentionally empty")
    status, bg = get('/api/room_backgrounds')
    configured = bg.get('configured') or {}
    check('no per-room backgrounds opted in', not configured, f"({sorted(configured)})")
    check('Temple Room is one-shots, not a bed',
          (rooms.get('Temple Room') or {}).get('effect') == 'TempleRoom-Ambient')

    async with AudioSpy(SPY_ROOMS) as spy:
        print("3) global maze ambience bed reaches a client")
        status, body = post('/api/start_maze_ambience', {})
        check('start maze ambience POST ok', status == 200, f"({body.get('message')})")
        await asyncio.sleep(1.0)
        beds = spy.take('start_maze_ambience')
        d = beds[-1]['data'] if beds else {}
        base = os.path.basename(d.get('file_name') or '')
        duration = d.get('duration_s')
        expected_loop = duration is not None and duration <= 45
        check('global bed started', bool(beds), f"(file={d.get('file_name')})")
        check('global bed came from the ambience pool', base in GLOBAL_BED_BASENAMES, f"({base})")
        check('loop flag follows duration policy',
              bool(beds) and d.get('loop') is expected_loop,
              f"(duration={duration}, loop={d.get('loop')})")

        print("4) Entrance ambient one-shot on demand")
        status, body = post('/api/ambient', {'room': 'Entrance'})
        check('room fire POST ok', status == 200, f"({body.get('message')})")
        await asyncio.sleep(0.5)
        shots = [m for m in spy.take('play_effect_audio')
                 if m['data'].get('effect_name') == 'Entrance-Ambient']
        files = [os.path.basename(m['data'].get('file_name') or '') for m in shots]
        check('one-shot arrived in Entrance', bool(shots), f'({files})')
        check('from the hallow/lightson pool',
              bool(files) and all(f in ENTRANCE_POOL for f in files), f'({files})')
        check('global bed NOT stopped by the one-shot', not spy.take('stop_maze_ambience'))

        print("5) maze-wide scatter")
        landed_here = []
        for _ in range(8):
            status, body = post('/api/ambient', {'maze': True})
            check_ok = status == 200
            if not check_ok:
                check('maze fire POST ok', False, f"({body.get('message')})")
                break
            await asyncio.sleep(0.5)
            landed_here = [m for m in spy.take('play_effect_audio')
                           if m['data'].get('effect_name') == 'MazeAmbient']
            if landed_here:
                break
        files = [os.path.basename(m['data'].get('file_name') or '') for m in landed_here]
        in_rooms = [m.get('room') for m in landed_here]
        check('a maze one-shot landed on our rooms within 8 firings',
              bool(landed_here), f'({files} in {in_rooms})')
        check('from the maze ambient pool',
              bool(files) and all(f.startswith(MAZE_PREFIXES) for f in files),
              f'({files})')
        check('never in the floor-show room', 'Cuddle Cross' not in in_rooms)
        post('/api/stop_maze_ambience', {})

    print("6) bad audition requests")
    status, _ = post('/api/ambient', {})
    check('empty POST -> 400', status == 400)
    status, _ = post('/api/ambient', {'room': 'Nowhere Special'})
    check('unknown room -> 400', status == 400)

    print(f"\n{'ALL PASS' if not FAILS else 'FAILURES: ' + ', '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)


asyncio.run(main())
