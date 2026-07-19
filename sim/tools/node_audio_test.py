#!/usr/bin/env python3
"""Unit test for the ESP32 node-audio downlink (node_audio_manager.py) and its
RemoteHostManager integration. No server or hardware needed:

  1. cue ids match what make_node_audio.py compiles into firmware
  2. WS command mirroring: play_effect_audio -> play_cue, music -> stream URL
     (percent-encoded), audio_stop -> announcement-only stop (music survives),
     stop_background_music -> media stop
  3. room=None broadcasts to every node room; unmapped rooms are untouched
  4. per-node FIFO lock keeps rapid-fire cues in dispatch order
  5. a dead node fails quietly (returns False, never raises, never blocks)
  6. RemoteHostManager: a node-only room (no WS client) reports success

Run: sim/.venv/bin/python sim/tools/node_audio_test.py   (from the repo root)
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import node_audio_manager as nam
from remote_host_manager import RemoteHostManager

FAILS = []


def check(name, ok, detail=''):
    print(f"  {'PASS' if ok else 'FAIL'}  {name} {detail}")
    if not ok:
        FAILS.append(name)


class FakeService:
    name = 'play_cue'


class FakeClient:
    def __init__(self, calls):
        self.calls = calls

    async def execute_service(self, svc, args):
        await asyncio.sleep(0.005)  # let another task interleave if it can
        self.calls.append(('cue', args['cue']))

    async def media_player_command(self, key, command=None, media_url=None,
                                   announcement=None):
        self.calls.append(('media', command, media_url, announcement))

    async def disconnect(self):
        pass


class FakeConn(nam._NodeConn):
    """Real lock/dispatch logic, fake wire."""
    def __init__(self, room, host, port):
        super().__init__(room, host, port)
        self.calls = []

    async def _ensure_connected(self):
        if self.client is None:
            self.client = FakeClient(self.calls)
            self.services = {'play_cue': FakeService()}
            self.media_key = 7


def make_manager(tmp_path):
    cfg = tmp_path / 'node_audio_config.json'
    cfg.write_text('''{
        "server_host": "10.0.0.2",
        "rooms": {
            "Monkey Room": {"host": "node-a", "port": 6072},
            "Temple Room": {"host": "node-b", "port": 6073}
        }
    }''')
    return nam.NodeAudioManager(config_file=str(cfg), conn_factory=FakeConn)


async def drain(manager):
    while manager._tasks:
        await asyncio.gather(*list(manager._tasks), return_exceptions=True)


async def run(tmp_path):
    check("cue_id sanitizes like the generator",
          nam.cue_id("The 7th Continent Soundscape - Area I.mp3")
          == "the_7th_continent_soundscape_area_i"
          and nam.cue_id("monkey-shrine-complete.mp3") == "monkey_shrine_complete")

    m = make_manager(tmp_path)
    monkey = m.rooms['monkey room']
    temple = m.rooms['temple room']
    check("enabled_for is case-insensitive; unmapped room is off",
          m.enabled_for("MONKEY room") and not m.enabled_for("Porto Room")
          and not m.enabled_for(None))

    # effect cue -> the mapped node only
    ok = m.handle_command("Monkey Room", "play_effect_audio",
                          {"file_name": "monkey-shrine-complete.mp3", "loop": False})
    await drain(m)
    check("play_effect_audio dispatches play_cue to its node",
          ok and monkey.calls == [('cue', 'monkey_shrine_complete')]
          and temple.calls == [])

    # unmapped room: untouched, reported unhandled
    check("unmapped room is a no-op",
          not m.handle_command("Porto Room", "play_effect_audio",
                               {"file_name": "x.mp3"}))

    # music broadcast: every node, URL percent-encoded
    m.handle_command(None, "start_background_music",
                     {"music_file": "The 7th Continent Soundscape - Area I.mp3"})
    await drain(m)
    url = ("http://10.0.0.2:5000/api/audio/"
           "The%207th%20Continent%20Soundscape%20-%20Area%20I.mp3")
    check("music broadcast hits every node with an encoded stream URL",
          monkey.calls[-1] == ('media', None, url, False)
          and temple.calls[-1] == ('media', None, url, False))

    # audio_stop stops cues only; stop_background_music stops the media pipeline
    m.handle_command("Monkey Room", "audio_stop", {})
    m.handle_command(None, "stop_background_music", {})
    await drain(m)
    from aioesphomeapi import MediaPlayerCommand
    check("audio_stop -> announcement stop; music stop -> media stop",
          ('media', MediaPlayerCommand.STOP, None, True) in monkey.calls
          and ('media', MediaPlayerCommand.STOP, None, False) in monkey.calls
          and ('media', MediaPlayerCommand.STOP, None, True) not in temple.calls)

    # rapid-fire ordering through the per-node lock
    monkey.calls.clear()
    for i in range(8):
        m.handle_command("Monkey Room", "play_effect_audio",
                         {"file_name": f"cue{i}.mp3"})
    await drain(m)
    check("8 rapid cues arrive in dispatch order",
          monkey.calls == [('cue', f'cue{i}') for i in range(8)])

    # dead node: real _NodeConn against a closed port — quiet False, no raise,
    # and once the backoff is armed further commands fail fast instead of
    # queueing connect timeouts behind the node lock
    import time
    dead = nam._NodeConn("Dead Room", "127.0.0.1", 1)
    result = await asyncio.wait_for(dead.play_cue("x"), timeout=15)
    t0 = time.monotonic()
    result2 = await asyncio.wait_for(dead.play_cue("y"), timeout=15)
    fast = time.monotonic() - t0
    check("dead node returns False without raising", result is False and result2 is False)
    check("backoff makes the next command fail fast", fast < 1.0, f"({fast:.3f}s)")

    # RemoteHostManager: node-only room (no WS clients) is a success, not an error
    rhm = RemoteHostManager(node_audio=m)
    ok = await rhm.send_audio_command("Monkey Room", "play_effect_audio",
                                     {"file_name": "monkey-shrine-complete.mp3"})
    await drain(m)
    not_ok = await rhm.send_audio_command("Porto Room", "play_effect_audio",
                                         {"file_name": "x.mp3"})
    check("send_audio_command: node-only room True, unmapped room False",
          ok is True and not_ok is False)


def main():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        asyncio.run(run(Path(td)))
    print(f"\n{'ALL PASS' if not FAILS else f'FAILURES: {FAILS}'}")
    sys.exit(1 if FAILS else 0)


if __name__ == '__main__':
    main()
