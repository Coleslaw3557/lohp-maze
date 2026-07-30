#!/usr/bin/env python3
"""Cuddle Cross following the floor projection (headless).

Exercises the contract the Pi renderer uses (projection_renderer.ServerReporter
-> POST /api/floor_event -> floor_show_manager.py):

  1. a LAVA show reporting active starts the looping bed on the ambience channel
  2. an effect taking the room over does NOT stop the bed (audio_stop is
     effect-only) — accents mix on top
  3. projection events fire accent audio + a capped light flare
  4. a second accent inside the cooldown is refused
  5. the maze theme's wash in the projection room stays under the projector cap
     with zero white, while an ordinary room is free to go bright
  6. the show going away stops the bed

The sim's own floor engine reports too (sim_ui._floor_loop), so the test first
cues its show: both reporters then agree the deck is live, exactly as on the
playa. That cue outlives the test — the bed stops by itself when the deck's
presence times out (~60 s), or immediately on the next theme with no sounds.

Run with the sim venv: sim/.venv/bin/python sim/tools/floor_audio_test.py [host]
"""
import asyncio
import json
import sys
import urllib.request

HOST = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
API = f'http://{HOST}:5000'
ROOM = 'Cuddle Cross'
CAP = 48          # theme_manager.ROOM_LIGHT_PROFILES ceiling (lava tightens to 44)
EFFECT_PEAK = 75  # effects.cuddle_puddle.PEAK
BREACH_POOL = {'lava2.wav', 'lava4.wav', 'lava5.wav'}
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


def get(path, timeout=10):
    with urllib.request.urlopen(API + path, timeout=timeout) as r:
        return r.status, json.loads(r.read())


def report(active=True, events=(), theme='lava'):
    """Stand in for one of the renderer's reports."""
    return post('/api/floor_event',
                {'theme': theme, 'active': active, 'events': list(events)})[1]


async def cue_sim_show():
    """Make the sim's own floor engine agree the deck is occupied, so its
    heartbeat doesn't report the show away underneath us."""
    import websockets
    async with websockets.connect(f'ws://{HOST}:5001/sim/projection') as ws:
        await ws.recv()  # hello
        await ws.send(json.dumps({'cue': 'floor-audio-test'}))
        await asyncio.sleep(0.3)


class AudioSpy:
    """The unit WS protocol, recording what the room is told to play."""

    def __init__(self):
        self.msgs = []
        self._task = None

    async def __aenter__(self):
        import websockets
        self.ws = await websockets.connect(f'ws://{HOST}:8765')
        await self.ws.send(json.dumps({
            'type': 'client_connected',
            'data': {'unit_name': 'FLOOR-AUDIO-TEST', 'associated_rooms': [ROOM]},
        }))
        self._task = asyncio.create_task(self._pump())
        await asyncio.sleep(1.0)  # let the room claim register
        return self

    async def _pump(self):
        while True:
            msg = json.loads(await self.ws.recv())
            self.msgs.append(msg)  # bind append AFTER the await: take() must
            # not be able to swap the list out from under a suspended pump

    async def __aexit__(self, *exc):
        self._task.cancel()
        await self.ws.close()

    def take(self, *types):
        got = [m for m in self.msgs if m.get('type') in types]
        self.msgs[:] = [m for m in self.msgs if m.get('type') not in types]
        return got


async def collect_frames(seconds, out):
    import websockets
    async with websockets.connect(f'ws://{HOST}:5001/sim/dmx') as ws:
        try:
            async with asyncio.timeout(seconds):
                while True:
                    out.append(bytes(json.loads(await ws.recv())['ch']))
        except TimeoutError:
            pass


def fixture(frame, start_address):
    base = start_address - 1
    return frame[base:base + 8]


async def main():
    status, layout = get('/api/room_layout')
    cuddle = [light['start_address'] for light in layout[ROOM]]
    other = [light['start_address'] for light in layout['Entrance']]
    check('room layout read', status == 200 and len(cuddle) == 2,
          f'({ROOM} fixtures @{cuddle})')
    await cue_sim_show()

    async with AudioSpy() as spy:
        print("1) LAVA show active -> looping bed on the ambience channel")
        body = report(active=True)
        await asyncio.sleep(0.5)
        beds = spy.take('play_room_ambience')
        d = beds[-1]['data'] if beds else {}
        check('bed started', bool(beds),
              f"(file={d.get('file_name')}, loop={d.get('loop')}, vol={d.get('volume')})")
        check('bed is the lava loop, looping',
              d.get('file_name') == 'lava.wav' and d.get('loop') is True)
        check('bed reported in state',
              body.get('bed') == 'Cuddle-Lava-Bed' and body.get('theme') == 'lava',
              f"({body.get('theme')}/{body.get('bed')})")
        if d.get('file_name'):
            with urllib.request.urlopen(f"{API}/api/audio/{d['file_name']}", timeout=10) as r:
                check('bed file downloadable', r.status == 200, f'({len(r.read())} bytes)')

        print("2) a room effect must not cut the bed")
        eff = asyncio.create_task(asyncio.to_thread(
            post, '/api/run_effect', {'room': ROOM, 'effect_name': 'CuddlePuddle'}))
        await asyncio.sleep(1.0)
        report(active=True)  # the show carries on under the effect
        await asyncio.sleep(0.5)
        check('no stop_room_ambience during an effect', not spy.take('stop_room_ambience'))
        check('bed not restarted mid-effect', not spy.take('play_room_ambience'))
        post('/api/stop_effect', {'room': ROOM})
        await eff
        await asyncio.sleep(0.3)
        check('per-room stop leaves the bed alone', not spy.take('stop_room_ambience'))

        print("3) projection events -> accent audio + light flare")
        frames = []
        collector = asyncio.create_task(collect_frames(3.0, frames))
        await asyncio.sleep(0.3)
        body = report(active=True, events=[{'e': 'monster_breach', 'x': 1, 'y': 2}])
        if body.get('accent') is None:  # the engine's own Kukulkan just went by
            await asyncio.sleep(3.5)
            body = report(active=True, events=[{'e': 'monster_breach', 'x': 1, 'y': 2}])
        check('breach fired an accent', body.get('accent') == 'Cuddle-Lava-Breach',
              f"(accent={body.get('accent')})")
        await collector
        await asyncio.sleep(0.2)
        files = [m['data'].get('file_name') for m in spy.take('play_effect_audio')]
        check('accent audio sent to the room', bool(files), f'({files})')
        check('accent came from the breach pool', set(files) <= BREACH_POOL, f'({files})')
        totals = {fixture(f, cuddle[0])[0] for f in frames}
        whites = {fixture(f, cuddle[0])[4] for f in frames}
        check('pars flared for the accent', len(totals) > 1, f'({len(totals)} distinct levels)')
        check('accent stayed under the projector cap', max(totals) <= EFFECT_PEAK,
              f'(peak {max(totals)})')
        check('accent used no white', whites == {0}, f'({sorted(whites)})')

        print("4) a second accent inside the cooldown is refused")
        body = report(active=True, events=[{'e': 'monster_breach'}])
        check('cooldown holds', body.get('accent') is None, f"(accent={body.get('accent')})")

        print("5) maze theme wash is capped in the projection room")
        # the accent flare must be off the fixtures first, or its 75 is what
        # we would be measuring instead of the theme's wash
        post('/api/stop_effect', {'room': ROOM})
        await asyncio.sleep(0.5)
        post('/api/set_theme', {'theme_name': 'NeonNightlife'})
        for attempt in range(3):
            # the sim's own show is live, so a real event can flare the pars
            # mid-measurement; that window measures the accent, not the wash
            spy.take('play_effect_audio')
            frames = []
            await collect_frames(3.0, frames)
            if not spy.take('play_effect_audio'):
                break
            print(f"     (an accent landed mid-window; re-measuring, attempt {attempt + 2})")
        post('/api/set_theme', {'theme_name': 'notheme'})
        cud = [fixture(f, cuddle[0]) for f in frames]
        ent = [fixture(f, other[0]) for f in frames]
        cud_peak = max((f[0] for f in cud), default=0)
        ent_peak = max((f[0] for f in ent), default=0)
        check('projection room stays under the cap', cud_peak <= CAP, f'(peak {cud_peak} <= {CAP})')
        check('projection room takes no white', {f[4] for f in cud} == {0})
        check('projection room is lit at all', cud_peak > 0, f'(peak {cud_peak})')
        check('ordinary rooms still go bright', ent_peak > CAP, f'(Entrance peak {ent_peak})')
        check('room wears the lava palette',
              max(f[1] for f in cud) > max(f[3] for f in cud),
              f'(r {max(f[1] for f in cud)} > b {max(f[3] for f in cud)})')

        print("6) show over -> bed stops")
        body = report(active=False)
        await asyncio.sleep(0.5)
        check('stop_room_ambience sent', bool(spy.take('stop_room_ambience')))
        check('bed cleared in state', body.get('bed') is None, f"(bed={body.get('bed')})")

    post('/api/stop_effect', {})
    print("\nnote: the sim's floor show is still cued, so its next report starts "
          "the bed again — it goes quiet on its own once presence times out.")
    print(f"{'ALL PASS' if not FAILS else 'FAILURES: ' + ', '.join(FAILS)}")
    sys.exit(1 if FAILS else 0)


asyncio.run(main())
