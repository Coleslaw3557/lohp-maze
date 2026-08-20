#!/usr/bin/env python3
"""Trigger virtual ESPHome sensor nodes over the native API.

Calls the node's `trip` action (someone entered), `vacate` action (a radar lost
them — the other half of the occupancy pair) or `press_button` action (rooms
with a physical button: photo-bomb, monkey), which publishes the matching
template binary_sensor or runs the matching script — the node firmware then runs
its real automation (debounce -> HTTP POST to the LoHP server), exactly as a
physical sensor event would.

On real radar hardware both edges come off the room's radar (LD2410C; Cuddle's
LD2450 exposes the same two outputs): enter on a
moving target, leave after `absence_timeout` with no target at all. Entrance and
Exit ToF hardware only trips; beam clear does not vacate the room. `visit`
replays the full occupancy shape for radar rooms.

Usage (with the esphome venv):
    .venv/bin/python harness.py list
    .venv/bin/python harness.py trip entrance
    .venv/bin/python harness.py trip all
    .venv/bin/python harness.py vacate cop-dodge
    .venv/bin/python harness.py visit cop-dodge       # enter, linger, leave
    .venv/bin/python harness.py visit cop-dodge 12    # linger 12s
    .venv/bin/python harness.py press photo-bomb
    .venv/bin/python harness.py press monkey

Requires: pip install aioesphomeapi
"""
import asyncio
import re
import sys
from pathlib import Path

ROOMS_DIR = Path(__file__).parent / 'rooms'


def node_ports():
    nodes = {}
    for f in sorted(ROOMS_DIR.glob('*.yaml')):
        text = f.read_text()
        port = re.search(r'api_port:\s*"(\d+)"', text)
        room = re.search(r'^\s+room:\s*"([^"]+)"', text, re.M)
        if port and room:
            nodes[f.stem] = {'port': int(port.group(1)), 'room': room.group(1)}
    return nodes


async def fire(name, info, action='trip', host='127.0.0.1', data=None):
    from aioesphomeapi import APIClient
    client = APIClient(host, info['port'], password='')
    try:
        await client.connect(login=True)
        _, services = await client.list_entities_services()
        svc = next((s for s in services if s.name == action), None)
        if not svc:
            print(f"  {name}: no '{action}' action exposed")
            return False
        result = client.execute_service(svc, data or {})
        if asyncio.iscoroutine(result):  # awaitable in newer aioesphomeapi
            await result
        await asyncio.sleep(0.3)  # let the call flush before disconnect
        print(f"  {name} ({info['room']}): {action} fired")
        return True
    except Exception as e:
        print(f"  {name} ({info['room']}): {type(e).__name__}: {e} — node not running?")
        return False
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass


async def main():
    nodes = node_ports()
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'list'

    if cmd == 'list':
        for name, info in nodes.items():
            print(f"  {name:24} room={info['room']:22} api_port={info['port']}")
        return

    if cmd in ('trip', 'press', 'vacate'):
        action = {'trip': 'trip', 'press': 'press_button', 'vacate': 'vacate'}[cmd]
        target = sys.argv[2] if len(sys.argv) > 2 else 'all'
        picked = nodes if target == 'all' else {target: nodes[target]}
        for name, info in picked.items():
            await fire(name, info, action)
            if target == 'all':
                await asyncio.sleep(1.0)
        return

    if cmd == 'visit':
        # A whole occupancy cycle: enter -> linger -> leave. The default linger
        # outlasts fire_effect's 5s cooldown so the leave POST lands after the
        # entry effect has finished on its own, which is the common real case.
        target = sys.argv[2]
        linger = float(sys.argv[3]) if len(sys.argv) > 3 else 8.0
        info = nodes[target]
        await fire(target, info, 'trip')
        print(f"  ... in the room for {linger}s")
        await asyncio.sleep(linger)
        await fire(target, info, 'vacate')
        return

    if cmd == 'call':
        # Generic action call on any node (bench hardware included, which
        # rooms/*.yaml doesn't know about), with key=value service args:
        #   harness.py call 192.168.252.87:6098 play_cue cue=monkey_shrine_complete
        target, action = sys.argv[2], sys.argv[3]
        host, _, port = target.partition(':')
        # digit values -> int: ESPHome int service args (press_moop n=2,
        # press_pad pad=1, ...) reject strings at the API layer
        data = {}
        for arg in sys.argv[4:]:
            k, _, v = arg.partition('=')
            data[k] = int(v) if re.fullmatch(r'-?\d+', v) else v
        await fire(target, {'port': int(port or 6053), 'room': host},
                   action, host=host, data=data)
        return

    print(__doc__)


asyncio.run(main())
