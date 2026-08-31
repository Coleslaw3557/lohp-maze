#!/usr/bin/env python3
"""Pair the Exterior BLE floods from the server side — no phone, no app.

Connects to the Exterior bridge node (ESPHome native API), fires its
pair_floods action and streams the node's log for the pairing window, then
prints the fastcon summary (found / confirmed per light). Floods must be
POWERED and in BLE range of the bridge; a flood that ever belonged to a
phone app needs the factory reset first (power-cycle 5x, it flashes).

The RUT blocks upstream->WLAN traffic, so this runs ON the Pi, inside the
server container (it has aioesphomeapi). From the dev box:

    ssh -p 2222 root@localhost \
      "docker exec -i lohp-server python3 - 192.168.252.77" \
      < tools/flood_pair.py

Idempotent: floods already on our key just re-confirm. Watch for
"CONFIRMED on our mesh key" lines — one per flood is success.
"""
import asyncio
import sys
import time

HOST = sys.argv[1] if len(sys.argv) > 1 else '192.168.252.77'
PORT = 6077
WINDOW_S = 40


async def main():
    from aioesphomeapi import APIClient
    cli = APIClient(HOST, PORT, None)
    await cli.connect(login=True)
    print(f"connected to {HOST}:{PORT}", flush=True)

    _, services = await cli.list_entities_services()
    pair = next((s for s in services if s.name == 'pair_floods'), None)
    if pair is None:
        print("FAIL: node has no pair_floods action (old firmware?)", flush=True)
        return 1

    hits = []

    def on_log(msg):
        line = getattr(msg, 'message', b'')
        if isinstance(line, bytes):
            line = line.decode(errors='replace')
        if any(k in line for k in ('fastcon', 'pairing', 'Pairing')):
            print(line, flush=True)
            hits.append(line)

    try:
        cli.subscribe_logs(on_log)
    except TypeError:
        await cli.subscribe_logs(on_log)

    cli.execute_service(pair, {})
    print(f"pair_floods fired; listening {WINDOW_S}s...", flush=True)
    await asyncio.sleep(WINDOW_S)

    confirmed = sum('CONFIRMED on our mesh key' in h for h in hits)
    found = sum('will assign id' in h for h in hits)
    print(f"RESULT: {found} unpaired flood(s) found, {confirmed} confirmed this run", flush=True)
    if confirmed == 0 and found == 0:
        print("Nothing heard: floods unpowered/out of range, or already paired "
              "(to us: fine; to an app: reset with 5x power-cycle and rerun).", flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.get_event_loop().run_until_complete(main()) or 0)
