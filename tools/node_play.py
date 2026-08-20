#!/usr/bin/env python3
"""Manually play one audio file on a room node's speaker (announcement path —
ducks the bed exactly like a show cue, then the bed recovers).

Run INSIDE the server container (it has aioesphomeapi + LAN access):

  ssh root@192.168.252.231 "docker exec lohp-server python tools/node_play.py cues/lava1.wav"
  ssh root@192.168.252.231 "docker exec lohp-server python tools/node_play.py cues/lava1.wav 192.168.252.66:6066"

arg 1 = path under /api/audio/ (see what nodes fetch: cues/<name>.wav,
        generated/ambience_loops/<...>.mp3, generated/node_streams/<...>.mp3)
arg 2 = node ip:port (default = Cuddle Cross). IP = api_port − 6000.
"""
import asyncio
import sys

import aioesphomeapi

SERVER = "192.168.252.231:5000"   # the production Pi (maze-network.md)
DEFAULT_NODE = "192.168.252.67:6067"  # Cuddle Cross


async def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1].lstrip("/")
    host, port = (sys.argv[2] if len(sys.argv) > 2 else DEFAULT_NODE).split(":")
    c = aioesphomeapi.APIClient(host, int(port), None)
    await c.connect(login=True)
    ents = (await c.list_entities_services())[0]
    players = [e for e in ents if getattr(e, "object_id", "").endswith("_audio")]
    if not players:
        sys.exit(f"{host}: no media_player entity found")
    url = f"http://{SERVER}/api/audio/{path}"
    c.media_player_command(players[0].key, media_url=url, announcement=True)
    await asyncio.sleep(2)   # let the command land before hanging up
    print(f"playing {path} on {host}")


asyncio.run(main())
