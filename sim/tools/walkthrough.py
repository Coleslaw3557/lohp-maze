#!/usr/bin/env python3
"""Scripted visitor walkthrough — a full-maze regression run.

Walks the canonical route from maze_layout.json and fires each room's real
trigger (the same POST its doorway sensor sends), staggered like a person
walking the maze. Overlapping effects in different rooms are normal and
intentional. With the sim page open in a browser you can watch the whole
run happen; headless it doubles as a regression test (all triggers must 200).

Run: sim/.venv/bin/python sim/tools/walkthrough.py [host] [--pace SECONDS]
"""
import json
import sys
import threading
import time
import urllib.request

HOST = 'localhost'
PACE = 4.0
args = [a for a in sys.argv[1:]]
if '--pace' in args:
    i = args.index('--pace')
    PACE = float(args[i + 1])
    del args[i:i + 2]
if args:
    HOST = args[0]

API = f'http://{HOST}:5000'
SIM = f'http://{HOST}:5001'


def get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


results = []
lock = threading.Lock()


def fire(name, path, data):
    started = time.time()
    try:
        req = urllib.request.Request(API + path, data=json.dumps(data).encode(),
                                     headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=60) as r:  # server holds until effect ends
            ok = r.status == 200
            msg = json.loads(r.read()).get('message', '')
    except Exception as e:
        ok, msg = False, str(e)
    with lock:
        results.append((name, ok, msg))
        print(f"  {'OK ' if ok else 'ERR'} {name:28} ({time.time() - started:4.1f}s) {msg}")


def main():
    cfg = get(f'{SIM}/sim/config')
    route = cfg['layout']['route']
    by_room = {}
    for t in cfg['triggers']:
        if t['room'] and t['type'] == 'laser' and t['room'] not in by_room:
            by_room[t['room']] = t

    print(f"Walkthrough: {len(route)} rooms, one visitor, ~{PACE}s per room\n")
    threads = []
    for room in route:
        trig = by_room.get(room)
        if not trig:
            print(f"  --  {room}: no doorway trigger configured")
            continue
        print(f"  >>  entering {room} -> {trig['action']['data'].get('effect_name')}")
        th = threading.Thread(target=fire, args=(trig['name'], trig['action']['path'], trig['action']['data']))
        th.start()
        threads.append(th)
        time.sleep(PACE)

    for th in threads:
        th.join()

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} triggers OK"
          + (f" — FAILURES: {[f[0] for f in failed]}" if failed else " — ALL PASS"))
    sys.exit(1 if failed else 0)


main()
