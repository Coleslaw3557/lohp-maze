#!/usr/bin/env python3
"""Trigger virtual ESPHome sensor nodes over the native API.

Calls the node's `trip` action (tripwire) or `press_button` action (rooms with
a physical button: photo-bomb, monkey), which publishes the matching template
binary_sensor — the node firmware then runs its real automation (debounce ->
HTTP POST to the LoHP server), exactly as a physical sensor event would.

Usage (with the esphome venv):
    .venv/bin/python harness.py list
    .venv/bin/python harness.py trip entrance
    .venv/bin/python harness.py trip all
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

    if cmd in ('trip', 'press'):
        action = 'trip' if cmd == 'trip' else 'press_button'
        target = sys.argv[2] if len(sys.argv) > 2 else 'all'
        picked = nodes if target == 'all' else {target: nodes[target]}
        for name, info in picked.items():
            await fire(name, info, action)
            if target == 'all':
                await asyncio.sleep(1.0)
        return

    if cmd == 'call':
        # Generic action call on any node (bench hardware included, which
        # rooms/*.yaml doesn't know about), with key=value service args:
        #   harness.py call 192.168.1.87:6098 play_cue cue=monkey_shrine_complete
        target, action = sys.argv[2], sys.argv[3]
        host, _, port = target.partition(':')
        data = dict(arg.split('=', 1) for arg in sys.argv[4:])
        await fire(target, {'port': int(port or 6053), 'room': host},
                   action, host=host, data=data)
        return

    print(__doc__)


asyncio.run(main())
