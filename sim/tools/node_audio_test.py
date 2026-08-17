#!/usr/bin/env python3
"""Unit test for the ESP32 node-audio downlink (node_audio_manager.py) and its
RemoteHostManager integration. No server or hardware needed:

  1. cue ids match the WAV filenames make_node_audio.py generates
  2. WS command mirroring: play_effect_audio streams the announcement cue URL
     WITHOUT touching the media pipeline (the bed keeps playing; the node's
     mixer ducks it); stop_maze_ambience -> media stop
  3. room=None broadcasts to every node room; unmapped rooms are untouched
  4. a room's own background bed owns the shared media pipeline; global maze
     ambience commands do not steal it, and bed stop resumes the maze bed
  5. per-node FIFO lock keeps rapid-fire cues in dispatch order
  6. a dead node fails quietly (returns False, never raises, never blocks)
  7. RemoteHostManager: a node-only room (no WS client) reports success
  8. beds with node_gain_baked pin the shared entity volume at 1.0; legacy
     payloads still ride the entity volume

Run: sim/.venv/bin/python sim/tools/node_audio_test.py   (from the repo root)
"""
import asyncio
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import node_audio_manager as nam
from remote_host_manager import RemoteHostManager

FAILS = []


def check(name, ok, detail=''):
    print(f"  {'PASS' if ok else 'FAIL'}  {name} {detail}")
    if not ok:
        FAILS.append(name)


class FakeClient:
    def __init__(self, calls):
        self.calls = calls

    async def media_player_command(self, key, command=None, media_url=None,
                                   announcement=None, volume=None):
        await asyncio.sleep(0.005)  # let another task interleave if it can
        self.calls.append(('media', command, media_url, announcement, volume))

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

    # effect cue -> the mapped node only, announcement ONLY (media untouched:
    # the bed keeps streaming and the node's mixer ducks it under the cue)
    ok = m.handle_command("Monkey Room", "play_effect_audio",
                          {"file_name": "monkey-shrine-complete.mp3", "loop": False})
    await drain(m)
    cue_url = "http://10.0.0.2:5000/api/audio/cues/monkey_shrine_complete.wav"
    check("play_effect_audio streams the cue URL without touching media",
          ok and monkey.calls == [('media', None, cue_url, True, 1.0)]
          and temple.calls == [])

    # unmapped room: untouched, reported unhandled
    check("unmapped room is a no-op",
          not m.handle_command("Porto Room", "play_effect_audio",
                               {"file_name": "x.mp3"}))

    # maze ambience broadcast: every node, URL percent-encoded
    m.handle_command(None, "start_maze_ambience",
                     {"file_name": "ambience/The 7th Continent Soundscape - Area I.mp3"})
    await drain(m)
    url = ("http://10.0.0.2:5000/api/audio/"
           "ambience/The%207th%20Continent%20Soundscape%20-%20Area%20I.mp3")
    check("maze ambience broadcast hits every node with an encoded stream URL",
          monkey.calls[-1] == ('media', None, url, False, 0.35)
          and temple.calls[-1] == ('media', None, url, False, 0.35))

    monkey.calls.clear()
    ok = m.handle_command("Monkey Room", "play_effect_audio",
                          {"file_name": "monkey-shrine-complete.mp3", "loop": False})
    await drain(m)
    check("cue over maze ambience leaves the bed stream alone",
          ok and monkey.calls == [('media', None, cue_url, True, 1.0)],
          f"({monkey.calls})")

    # prepared node loop: browsers still see file_name, but ESP nodes should
    # receive the long generated bed and should not arm a replay timer.
    monkey.calls.clear()
    m.handle_command("Monkey Room", "start_maze_ambience", {
        "file_name": "short.wav",
        "node_file_name": "generated/ambience_loops/short_long.mp3",
        "loop": True,
        "node_loop": False,
        "duration_s": 8.0,
        "node_duration_s": 240.0,
        "play_for_s": 240.0,
        "volume": 0.3,
    })
    await drain(m)
    check("prepared node ambience uses generated file and skips repeat",
          monkey.calls[-1] == ('media', None,
                               "http://10.0.0.2:5000/api/audio/"
                               "generated/ambience_loops/short_long.mp3",
                               False, 0.3)
          and monkey not in m._repeat_tasks,
          f"({monkey.calls[-1:]}, repeats={m._repeat_tasks})")

    monkey.calls.clear()
    m.handle_command("Monkey Room", "start_maze_ambience", {
        "file_name": "ambience/synced.mp3",
        "node_file_name": "generated/node_streams/synced.mp3",
        "loop": False,
        "duration_s": 120.0,
        "node_duration_s": 120.0,
        "play_for_s": 122.0,
        "sync_started_at_s": time.monotonic() - 31.0,
    })
    await drain(m)
    parsed = urlparse(monkey.calls[-1][2])
    offset = float(parse_qs(parsed.query).get("offset_s", ["0"])[0])
    check("synced node ambience resumes from the shared maze-bed offset",
          parsed.path.endswith("/api/audio/generated/node_streams/synced.mp3")
          and 30.0 <= offset <= 32.0,
          f"({monkey.calls[-1]})")

    monkey.calls.clear()
    temple.calls.clear()
    monkey.client = object()
    temple.client = None
    m.maze_ambience_file = "ambience/synced.mp3"
    m.maze_ambience_data = {
        "file_name": "ambience/synced.mp3",
        "node_file_name": "generated/node_streams/synced.mp3",
        "loop": False,
        "duration_s": 120.0,
        "node_duration_s": 120.0,
        "play_for_s": 122.0,
        "sync_started_at_s": time.monotonic() - 12.0,
    }
    check("maze ambience retry targets disconnected nodes only",
          m.retry_maze_ambience_on_disconnected_nodes() is True)
    await drain(m)
    check("maze ambience retry does not restart connected nodes",
          monkey.calls == [] and len(temple.calls) == 1
          and "offset_s=" in temple.calls[0][2],
          f"(monkey={monkey.calls}, temple={temple.calls})")
    monkey.client = None

    # audio_stop stops cues only; stop_maze_ambience stops the media pipeline
    m.handle_command("Monkey Room", "audio_stop", {})
    m.handle_command(None, "stop_maze_ambience", {})
    await drain(m)
    from aioesphomeapi import MediaPlayerCommand
    check("audio_stop -> announcement stop; maze ambience stop -> media stop",
          ('media', MediaPlayerCommand.STOP, None, True, None) in monkey.calls
          and ('media', MediaPlayerCommand.STOP, None, False, None) in monkey.calls
          and ('media', MediaPlayerCommand.STOP, None, True, None) not in temple.calls)

    # bed vs maze ambience on the node's ONE media pipeline: the room background
    # overrides maze ambience for its node, ambience start/stop never steal the
    # pipeline from a bed, and the current track resumes when the bed stops
    monkey.calls.clear()
    temple.calls.clear()
    base = "http://10.0.0.2:5000/api/audio/"
    m.handle_command(None, "start_maze_ambience", {"file_name": "song.mp3"})
    m.handle_command("Monkey Room", "play_room_ambience", {"file_name": "bed.wav"})
    m.handle_command(None, "start_maze_ambience", {"file_name": "next.mp3"})
    m.handle_command(None, "stop_maze_ambience", {})
    m.handle_command(None, "start_maze_ambience", {"file_name": "song2.mp3"})
    m.handle_command("Monkey Room", "stop_room_ambience", {})
    await drain(m)
    check("bed-active node: maze ambience start and stop never touch the pipeline",
          monkey.calls[:2] == [('media', None, base + "song.mp3", False, 0.35),
                               ('media', None, base + "bed.wav", False, 0.35)]
          and monkey.calls[2] == ('media', None, base + "song2.mp3", False, 0.35),
          f"({monkey.calls})")
    check("bed stop hands the pipeline back to the current maze ambience",
          len(monkey.calls) == 3 and not monkey.bed_active)
    check("bed-free node keeps following maze ambience commands",
          temple.calls == [('media', None, base + "song.mp3", False, 0.35),
                           ('media', None, base + "next.mp3", False, 0.35),
                           ('media', MediaPlayerCommand.STOP, None, False, None),
                           ('media', None, base + "song2.mp3", False, 0.35)],
          f"({temple.calls})")

    # with maze ambience OFF, a bed stop stops the pipeline instead of resuming
    monkey.calls.clear()
    m.handle_command(None, "stop_maze_ambience", {})
    m.handle_command("Monkey Room", "play_room_ambience", {"file_name": "bed.wav"})
    m.handle_command("Monkey Room", "stop_room_ambience", {})
    await drain(m)
    check("bed stop with maze ambience off -> media stop, no phantom resume",
          monkey.calls[-1] == ('media', MediaPlayerCommand.STOP, None, False, None),
          f"({monkey.calls})")

    # rapid-fire ordering through the per-node lock
    monkey.calls.clear()
    for i in range(8):
        m.handle_command("Monkey Room", "play_effect_audio",
                         {"file_name": f"cue{i}.mp3"})
    await drain(m)
    check("8 rapid cues arrive in dispatch order with no media stops",
          monkey.calls == [('media', None,
                            f"http://10.0.0.2:5000/api/audio/cues/cue{i}.wav",
                            True, 1.0) for i in range(8)])

    # node_gain_baked beds pin the shared entity volume at 1.0 (gain lives in
    # the generated stream); legacy payloads still ride the entity volume
    monkey.calls.clear()
    m.handle_command("Monkey Room", "play_room_ambience", {
        "file_name": "bed.wav",
        "node_file_name": "generated/node_streams/bed.mp3",
        "node_gain_baked": True,
        "volume": 0.3,
    })
    await drain(m)
    check("gain-baked bed plays at entity volume 1.0",
          monkey.calls[-1] == ('media', None,
                               "http://10.0.0.2:5000/api/audio/"
                               "generated/node_streams/bed.mp3", False, 1.0),
          f"({monkey.calls[-1:]})")
    m.handle_command("Monkey Room", "stop_room_ambience", {})
    m.handle_command(None, "stop_maze_ambience", {})
    await drain(m)

    # dead node: real _NodeConn against a closed port — quiet False, no raise,
    # and once the backoff is armed further commands fail fast instead of
    # queueing connect timeouts behind the node lock
    dead = nam._NodeConn("Dead Room", "127.0.0.1", 1)
    result = await asyncio.wait_for(
        dead.play_announcement("http://10.0.0.2:5000/api/audio/cues/x.wav"),
        timeout=15)
    t0 = time.monotonic()
    result2 = await asyncio.wait_for(
        dead.play_announcement("http://10.0.0.2:5000/api/audio/cues/y.wav"),
        timeout=15)
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
