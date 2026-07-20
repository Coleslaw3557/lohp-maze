"""Verify two WS clients from the SAME IP both stay registered and both
receive a claimed room's audio (the old IP-keyed registry dropped one)."""
import asyncio
import json
import urllib.request

import websockets

API = "http://127.0.0.1:5000"


def post(path, body):
    req = urllib.request.Request(API + path, json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=30).read()


def get(path):
    return json.loads(urllib.request.urlopen(API + path, timeout=10).read())


async def unit(name):
    ws = await websockets.connect("ws://127.0.0.1:8765")
    await ws.send(json.dumps({"type": "client_connected",
                              "data": {"unit_name": name, "associated_rooms": ["Entrance"]}}))
    got = []

    async def listen():
        try:
            async for m in ws:
                got.append(json.loads(m))
        except websockets.ConnectionClosed:
            pass

    return ws, got, asyncio.create_task(listen())


async def main():
    fails = []
    ws_a, got_a, t_a = await unit("SAME-IP-A")
    ws_b, got_b, t_b = await unit("SAME-IP-B")
    await asyncio.sleep(0.7)

    names = [c["name"] for c in get("/api/connected_clients")]
    both_registered = "SAME-IP-A" in names and "SAME-IP-B" in names
    print(("PASS" if both_registered else "FAIL") +
          f"  both same-IP clients registered ({names})")
    if not both_registered:
        fails.append("registry")

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, post, "/api/run_effect",
                               {"room": "Entrance", "effect_name": "Lightning"})
    await asyncio.sleep(0.7)

    for label, got in (("A", got_a), ("B", got_b)):
        plays = [m for m in got if m.get("type") == "play_effect_audio"
                 and m.get("room") == "Entrance"]
        ok = len(plays) == 1
        print(("PASS" if ok else "FAIL") +
              f"  client {label} received Entrance play_effect_audio x{len(plays)}")
        if not ok:
            fails.append(label)

    # A's disconnect must not unregister B (old code could strand/mis-drop entries)
    await ws_a.close()
    await asyncio.sleep(0.5)
    names = [c["name"] for c in get("/api/connected_clients")]
    ok = "SAME-IP-A" not in names and "SAME-IP-B" in names
    print(("PASS" if ok else "FAIL") + f"  A's disconnect removed only A ({names})")
    if not ok:
        fails.append("disconnect")

    await ws_b.close()
    for t in (t_a, t_b):
        t.cancel()
    print("ALL PASS" if not fails else f"FAILURES: {fails}")
    return 0 if not fails else 1


raise SystemExit(asyncio.run(main()))
