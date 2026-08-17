#!/usr/bin/env python3
"""Occupancy-pair test for the simulator (headless).

Radar room sensors report two facts (triggers.json presence triggers): enter
fires the room's effect, leave fires
`/api/room_vacated`. This checks the leave half actually does what the room
needs, which the effect-duration timeout used to do by accident:

  1. enter runs the room's effect and the unit hears its audio
  2. leave DURING an effect cancels it, silences the room, and hands the
     fixture back to the theme
  3. leave AFTER the effect already finished still silences the room (looping
     or long audio outlives the lighting) and still leaves it on the theme —
     the resume is unconditional for exactly this case
  4. leave with no visitor and leave twice are both harmless
  5. a whole visit never touches maze ambience: effect audio MIXES over it
     rather than replacing it, so the maze bed playing before someone walked
     in is still playing after they leave
  6. between the entry effect ending and the leave, the room wears its
     OCCUPIED colour lock: the theme keeps animating it, but pinned to the
     room's own profile colour (theme_manager.OCCUPIED_MIX); the leave
     releases it back to the plain room blend
  7. a leave with no room is rejected

Run with the sim running: sim/.venv/bin/python sim/tools/occupancy_test.py [host]
"""
import asyncio
import json
import os
import sys
import urllib.error
import urllib.request

HOST = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
API = f'http://{HOST}:5000'
ROOM = 'Cop Dodge'
FAILS = []


def check(name, ok, detail=''):
    print(f"  {'PASS' if ok else 'FAIL'}  {name} {detail}")
    if not ok:
        FAILS.append(name)


def post(path, data, timeout=60):
    req = urllib.request.Request(API + path, data=json.dumps(data).encode(),
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')


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
        self.messages = []  # (type, room-or-None, effect-or-None)
        self.task = None

    async def _run(self):
        import websockets
        async with websockets.connect(f'ws://{HOST}:8765') as ws:
            await ws.send(json.dumps({
                'type': 'client_connected',
                'data': {'unit_name': 'OCCUPANCY-UNIT', 'associated_rooms': self.rooms},
            }))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get('type') in ('play_effect_audio', 'audio_stop',
                                       'start_maze_ambience', 'stop_maze_ambience'):
                    data = msg.get('data') or {}
                    self.messages.append((msg['type'], msg.get('room'), data.get('effect_name')))

    def start(self):
        self.task = asyncio.create_task(self._run())

    async def stop(self):
        self.task.cancel()
        try:
            await self.task
        except (asyncio.CancelledError, Exception):
            pass

    def for_room(self, room):
            return [(t, r, e) for t, r, e in self.messages if r == room or r is None]


def room_channel(room):
    """Index into the DMX frame of the room's first fixture's first channel."""
    lights = get('/api/rooms')[room]
    return lights[0]['start_address'] - 1


async def theme_animates(channel, seconds=2.0):
    frames = []
    await collect_frames(seconds, frames)
    return len({f[channel] for f in frames if len(f) > channel})


def entry_effect(room):
    """The room's real entry effect, from the canonical trigger map — so the test
    exercises the configured path rather than an arbitrary effect."""
    path = os.path.join(os.path.dirname(__file__), '..', '..', 'triggers.json')
    with open(path) as f:
        for trig in json.load(f)['triggers']:
            if trig['room'] == room and trig['type'] == 'presence':
                return trig['action']['data']['effect_name']
    raise SystemExit(f"no presence trigger for {room} in triggers.json")


async def main():
    rooms = list(get('/api/rooms').keys())
    channel = room_channel(ROOM)
    effect = entry_effect(ROOM)
    duration = get('/api/effects_details')[effect].get('duration')
    if duration < 5:
        raise SystemExit(f"{ROOM}'s entry effect {effect} is only {duration}s — "
                         f"too short to land a leave mid-effect; pick another room")
    print(f"Room {ROOM} (dmx ch {channel + 1}); entry effect {effect} ({duration}s)\n")

    unit = FakeUnit(rooms)
    unit.start()
    await asyncio.sleep(1.0)  # let the room claims register

    status, body = post('/api/set_theme', {'theme_name': 'DeepCanopy'})
    check('theme running for the test', status == 200, body.get('message', ''))
    await asyncio.sleep(1.0)

    print("1) enter runs the room's effect")
    unit.messages.clear()
    enter = await post_bg('/api/run_effect', {'room': ROOM, 'effect_name': effect})
    await asyncio.sleep(1.0)
    seq = unit.for_room(ROOM)
    check('unit heard the effect audio',
          any(t == 'play_effect_audio' for t, _, _ in seq), f'({seq})')

    print("2) leave DURING the effect cancels it and restores the theme")
    status, body = post('/api/room_vacated', {'room': ROOM})
    check('room_vacated accepted', status == 200, body.get('message', ''))
    enter_status, enter_body = await asyncio.wait_for(enter, 60)
    check('the held enter request completed', enter_status == 200,
          f"({enter_status} {enter_body.get('message', '')})")
    await asyncio.sleep(0.5)
    seq = unit.for_room(ROOM)
    entry_play_idx = next((i for i, (t, _, e) in enumerate(seq)
                           if t == 'play_effect_audio' and e == effect), None)
    stop_idx = next((i for i, (t, _, _) in enumerate(seq)
                     if t == 'audio_stop' and entry_play_idx is not None and i > entry_play_idx), None)
    check('entry audio stopped on leave',
          stop_idx is not None, f'({seq})')
    distinct = await theme_animates(channel)
    check('theme animates the room again after leave', distinct > 1,
          f'({distinct} distinct values on ch {channel + 1})')

    print("3) leave AFTER the effect already finished")
    unit.messages.clear()
    status, _ = post('/api/run_effect', {'room': ROOM, 'effect_name': 'WrongAnswer'})
    check('short effect ran to completion', status == 200)
    await asyncio.sleep(0.5)
    unit.messages.clear()
    status, body = post('/api/room_vacated', {'room': ROOM})
    check('room_vacated accepted post-effect', status == 200, body.get('message', ''))
    await asyncio.sleep(0.5)
    seq = unit.for_room(ROOM)
    check('lingering audio still stopped',
          any(t == 'audio_stop' for t, _, _ in seq), f'({seq})')
    distinct = await theme_animates(channel)
    check('room still on the theme', distinct > 1,
          f'({distinct} distinct values on ch {channel + 1})')

    print("4) leave with no visitor / leave twice")
    status1, _ = post('/api/room_vacated', {'room': ROOM})
    status2, _ = post('/api/room_vacated', {'room': ROOM})
    check('repeated leaves are harmless', (status1, status2) == (200, 200),
          f'({status1}, {status2})')
    distinct = await theme_animates(channel)
    check('theme survives repeated leaves', distinct > 1, f'({distinct} distinct values)')

    print("5) a visit never touches maze ambience")
    status, body = post('/api/start_maze_ambience', {})
    ambience_started = status == 200 and 'error' not in str(body.get('status', ''))
    if not ambience_started:
        print(f"  SKIP  no maze ambience available ({body.get('message', '')})")
    else:
        await asyncio.sleep(0.5)
        unit.messages.clear()
        visit = await post_bg('/api/run_effect', {'room': ROOM, 'effect_name': effect})
        await asyncio.sleep(1.0)
        post('/api/room_vacated', {'room': ROOM})
        await asyncio.wait_for(visit, 60)
        await asyncio.sleep(0.5)
        stops = [t for t, _, _ in unit.messages if t == 'stop_maze_ambience']
        check('maze ambience untouched by enter+leave (effects mix over it)', not stops,
              f'({len(stops)} stop_maze_ambience during the visit)')
        post('/api/stop_maze_ambience', {})

    print("6) occupied room holds its own colour after the effect; leave releases it")
    import colorsys
    profile_hue = colorsys.rgb_to_hsv(35 / 255, 75 / 255, 230 / 255)[0]  # Cop Dodge profile rgb

    async def room_hue_distance(seconds=2.0):
        """Mean hue distance of the room's lit frames from its profile colour."""
        frames = []
        await collect_frames(seconds, frames)
        dists = []
        for f in frames:
            r, g, b = f[channel + 1], f[channel + 2], f[channel + 3]
            if max(r, g, b) < 5:
                continue
            h = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)[0]
            dists.append(abs((h - profile_hue + 0.5) % 1.0 - 0.5))
        return (sum(dists) / len(dists)) if dists else None

    enter = await post_bg('/api/run_effect', {'room': ROOM, 'effect_name': effect})
    enter_status, _ = await asyncio.wait_for(enter, 60)  # runs the whole entry effect
    check('entry effect ran to completion', enter_status == 200)
    await asyncio.sleep(1.5)  # smoother settles onto the held look
    occ_dist = await room_hue_distance()
    check('room pinned near its profile colour while occupied',
          occ_dist is not None and occ_dist <= 0.07, f'(hue dist {occ_dist})')
    distinct = await theme_animates(channel)
    check('held look still breathes with the theme', distinct > 1,
          f'({distinct} distinct values on ch {channel + 1})')
    post('/api/room_vacated', {'room': ROOM})
    await asyncio.sleep(2.0)  # smoother walks back to the plain blend
    plain_dist = await room_hue_distance(3.0)
    # Relative, not absolute: where the theme hue happens to be wandering
    # decides the absolute distances, but a released room must sit clearly
    # farther from its profile colour than a pinned one.
    check('leave releases the room to the plain theme blend',
          plain_dist is not None and plain_dist >= occ_dist + 0.03,
          f'(hue dist pinned {occ_dist:.3f} -> released {plain_dist:.3f})')

    print("7) malformed leave")
    status, body = post('/api/room_vacated', {})
    check('leave with no room is rejected', status == 400, body.get('message', ''))

    await unit.stop()
    print(f"\n{'ALL PASS' if not FAILS else 'FAILURES: ' + ', '.join(FAILS)}")
    return 1 if FAILS else 0


sys.exit(asyncio.run(main()))
