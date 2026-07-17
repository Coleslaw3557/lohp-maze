#!/usr/bin/env python3
"""Concurrency stress test for the simulator (headless).

Simulates many people in the maze pushing buttons and tripping sensors at
once, and checks the invariants that used to break:

  1. same-room trigger storm: every POST succeeds, and the *last* audio
     command a unit receives for the room is a play (a stale stop must never
     kill the newest effect's audio)
  2. after the storm the theme animates the room's fixture again (no leaked
     interrupt claim, no unbalanced theme pause)
  3. all-rooms effect racing single-room triggers: all succeed, server recovers
  4. explicit stop during an effect ends with audio_stop as the last command
  5. concurrent start_music hammering leaves the server healthy

Run with the sim running: sim/.venv/bin/python sim/tools/concurrency_test.py [host]
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


def post(path, data, timeout=60):
    req = urllib.request.Request(API + path, data=json.dumps(data).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read())


def get(path):
    with urllib.request.urlopen(API + path, timeout=10) as r:
        return json.loads(r.read())


async def post_bg(path, data):
    """The server holds run_effect open until the effect ends/is superseded."""
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


class FakeUnit:
    """Speaks the room-unit WS protocol and records every audio command."""

    def __init__(self, rooms):
        self.rooms = rooms
        self.messages = []  # (type, room-or-None)
        self.task = None

    async def _run(self):
        import websockets
        async with websockets.connect(f'ws://{HOST}:8765') as ws:
            await ws.send(json.dumps({
                'type': 'client_connected',
                'data': {'unit_name': 'STRESS-UNIT', 'associated_rooms': self.rooms},
            }))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get('type') in ('play_effect_audio', 'audio_stop',
                                       'start_background_music', 'stop_background_music'):
                    self.messages.append((msg['type'], msg.get('room')))

    def start(self):
        self.task = asyncio.create_task(self._run())

    async def stop(self):
        self.task.cancel()
        try:
            await self.task
        except (asyncio.CancelledError, Exception):
            pass

    def for_room(self, room):
        return [(t, r) for t, r in self.messages if r == room or r is None]


async def main():
    rooms = list(get('/api/rooms').keys())
    unit = FakeUnit(rooms)
    unit.start()
    await asyncio.sleep(1.0)  # let the room claims register

    print("1) same-room trigger storm (6 rapid triggers, Entrance)")
    unit.messages.clear()
    reqs = []
    for i in range(6):
        effect = 'Lightning' if i % 2 else 'WrongAnswer'
        reqs.append(await post_bg('/api/run_effect', {'room': 'Entrance', 'effect_name': effect}))
        await asyncio.sleep(0.15)
    results = await asyncio.gather(*(asyncio.wait_for(r, 60) for r in reqs))
    check('all storm POSTs succeed', all(s == 200 for s, _ in results),
          f'({[s for s, _ in results]})')
    await asyncio.sleep(0.5)  # let any straggler commands arrive
    seq = unit.for_room('Entrance')
    check('unit got play commands', sum(1 for t, _ in seq if t == 'play_effect_audio') >= 6,
          f'({len(seq)} audio commands)')
    check('last audio command is a play (newest effect keeps its audio)',
          bool(seq) and seq[-1][0] == 'play_effect_audio', f'(last={seq[-1] if seq else None})')

    print("2) theme recovers the stormed room's fixture")
    status, body = post('/api/set_theme', {'theme_name': 'NeonNightlife'})
    check('set_theme accepted', status == 200, body.get('message', ''))
    await asyncio.sleep(4.0)  # let the last storm effect finish and theme resume
    frames = []
    await collect_frames(2, frames)
    entrance_values = {f[0] for f in frames}  # fixture @1, first channel
    check('theme animates Entrance fixture again', len(entrance_values) > 1,
          f'({len(entrance_values)} distinct values)')

    print("3) all-rooms effect racing single-room triggers")
    unit.messages.clear()
    mixed = [await post_bg('/api/run_effect_all_rooms', {'effect_name': 'WrongAnswer'})]
    await asyncio.sleep(0.05)
    mixed.append(await post_bg('/api/run_effect', {'room': 'Gate', 'effect_name': 'Lightning'}))
    mixed.append(await post_bg('/api/run_effect', {'room': 'Exit', 'effect_name': 'CorrectAnswer'}))
    await asyncio.sleep(0.2)
    mixed.append(await post_bg('/api/run_effect_all_rooms', {'effect_name': 'CorrectAnswer'}))
    results = await asyncio.gather(*(asyncio.wait_for(r, 60) for r in mixed))
    check('mixed storm all succeed', all(s == 200 for s, _ in results),
          f'({[s for s, _ in results]})')
    status, body = post('/api/run_effect', {'room': 'Entrance', 'effect_name': 'WrongAnswer'})
    check('server healthy after mixed storm', status == 200, body.get('message', ''))

    print("4) explicit stop during an effect")
    unit.messages.clear()
    eff = await post_bg('/api/run_effect', {'room': 'Cop Dodge', 'effect_name': 'PoliceLights'})
    await asyncio.sleep(0.5)
    status, body = post('/api/stop_effect', {'room': 'Cop Dodge'})
    check('stop_effect accepted', status == 200, body.get('message', ''))
    status, body = await asyncio.wait_for(eff, 30)
    check('superseded run_effect returns success', status == 200, body.get('message', ''))
    await asyncio.sleep(0.3)
    seq = unit.for_room('Cop Dodge')
    check('stop ends with audio_stop', bool(seq) and seq[-1][0] == 'audio_stop',
          f'(last={seq[-1] if seq else None})')

    print("4b) stop-all silences audio that outlived its lights")
    unit.messages.clear()
    # WrongAnswer lights last 1.5s; wait them out so no lighting task remains
    status, _ = post('/api/run_effect', {'room': 'Gate', 'effect_name': 'WrongAnswer'})
    await asyncio.sleep(0.3)
    status, body = post('/api/stop_effect', {})  # stop all rooms
    check('stop-all accepted', status == 200, body.get('message', ''))
    await asyncio.sleep(0.3)
    check('stop-all broadcasts audio_stop to every unit',
          ('audio_stop', None) in unit.messages, f'({unit.messages[-3:]})')
    unit.messages.clear()
    status, _ = post('/api/stop_effect', {'room': 'Gate'})  # idle room, no task
    await asyncio.sleep(0.3)
    check('per-room stop reaches an idle room (audio may outlive lights)',
          ('audio_stop', 'Gate') in unit.messages, f'({unit.messages})')

    print("5) concurrent start_music hammering")
    unit.messages.clear()
    music_reqs = [await post_bg('/api/start_music', {}) for _ in range(5)]
    results = await asyncio.gather(*(asyncio.wait_for(r, 30) for r in music_reqs))
    check('all start_music succeed', all(s == 200 for s, _ in results),
          f'({[s for s, _ in results]})')
    status, body = post('/api/stop_music', {})
    check('stop_music succeeds', status == 200, body.get('message', ''))
    await asyncio.sleep(0.3)
    starts = sum(1 for t, _ in unit.messages if t == 'start_background_music')
    stops = sum(1 for t, _ in unit.messages if t == 'stop_background_music')
    check('music commands arrived in order (starts then one stop)',
          starts == 5 and stops == 1 and unit.messages[-1][0] == 'stop_background_music',
          f'({starts} starts, {stops} stops)')

    print("6) no stuck frame after an effect that ends on a bright hold (no theme)")
    post('/api/set_theme', {'theme_name': 'notheme'})
    await asyncio.sleep(0.5)
    # GateGreeters' final step is warm white; completion must not latch it
    status, _ = post('/api/run_effect', {'room': 'Entrance', 'effect_name': 'GateGreeters'})
    check('GateGreeters completed', status == 200)
    await asyncio.sleep(0.5)
    frames = []
    await collect_frames(2.5, frames)
    stuck = any(any(f[i] for i in range(8)) for f in frames[-3:])
    check('Entrance fixture returns to black, not stuck white',
          bool(frames) and not stuck,
          f'(last frame ch1-8: {list(frames[-1][:8]) if frames else "no frames"})')

    # cleanup
    post('/api/stop_effect', {})
    await unit.stop()

    print(f"\n{'ALL PASS' if not FAILS else 'FAILURES: ' + ', '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)


asyncio.run(main())
