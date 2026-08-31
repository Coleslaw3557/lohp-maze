#!/usr/bin/env python3
"""Standalone field-calibration server — runs on the DEV BOX, not the Pi.

2026-08-30 (Tim): the production Pi must stay lean, so the /calibrate tool
moved here. The phone still opens it from inside the maze; everything rides
the Pi's reverse SSH tunnel:

  phone (LOHP-ESP) -> Pi 192.168.252.231:5001  [sshd remote-forward]
      -> dev box localhost:5001 (this app)
  this app -> nodes: localhost:1$PORT [ssh local-forwards to .252.x:$PORT]

tools/calibrate/run-calibrate.sh starts the plumbing ssh (one session holds
the -R and all the -L forwards; Pi sshd needs GatewayPorts clientspecified)
and this server under the sim venv:

  tools/calibrate/run-calibrate.sh          # start both, nohup'd
  tools/calibrate/run-calibrate.sh stop

This app keeps its OWN aioesphomeapi client per node (second client beside
the Pi server's audio connection — the ESPHome API accepts several).
Latency: every poll crosses playa camp WiFi + home internet twice; the page
already tolerates slow polls.

Captures/tuning journal land in data/calibration/ under the repo root on the
dev box (data/ is gitignored). Same API shape the Pi briefly served:
  GET  /calibrate                      the phone page
  GET  /api/calibration/rooms|state|captures
  POST /api/calibration/write|capture/start|stop|mark
  POST /api/calibration/guided/start|cancel   server-timed walk-through + verdict
Tuning writes still DIE WITH A NODE REBOOT until baked into the room YAML.
"""
import asyncio
import inspect
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone

from aioesphomeapi import APIClient
from quart import Quart, jsonify, request, send_file

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('calibrate')
logging.getLogger('aioesphomeapi.connection').setLevel(logging.ERROR)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
DATA_DIR = os.path.join(REPO, 'data', 'calibration')
LISTEN_PORT = int(os.environ.get('CAL_PORT', '5001'))
# Node API reached through the plumbing ssh's -L forwards: 6062 -> 16062.
FORWARD_BASE = int(os.environ.get('CAL_FORWARD_BASE', '10000'))
DIRECT = os.environ.get('CAL_DIRECT') == '1'   # bench-on-LAN mode: dial nodes directly

CONNECT_TIMEOUT = 12
PROBE_TIMEOUT = 10       # tunnel adds two internet RTTs on top of playa RF
KEEPALIVE_TICK_S = 12
KEEPALIVE_MAX_BACKOFF_S = 60
SAMPLE_PERIOD_S = 0.5
MAX_CAPTURE_S = 900
STATE_TYPES = ('BinarySensorInfo', 'SensorInfo', 'NumberInfo', 'SelectInfo',
               'SwitchInfo', 'TextSensorInfo')

# Guided walk-through (2026-08-31): Tim carries the phone room to room and taps
# GO; the SERVER runs the timed sequence (phone WiFi dropouts can't break it),
# marks each phase into the normal capture jsonl, then judges the presence /
# moving traces and stores a plain-language verdict. Detailed gate tuning still
# happens later from the captured files.
GUIDED_STEPS = [
    # (id, phone headline, detail line, seconds)
    # 25s: slow exit + the radar's own decay (5s module + 5s delayed_off) can
    # eat 15s before a true empty shows — only the last 6s are judged.
    ('out',   'Step OUT of the room',      'wait just outside the doorway', 25),
    ('still', 'Walk in — STAND STILL',     'middle of the room — freeze', 15),
    ('move',  'WALK around the room',      'cover the corners too', 15),
    ('leave', 'Walk on to the NEXT room',  "leave and don't come back", 20),
]
# Cuddle's 60s absence timer means presence stays ON for a minute after an
# exit — its empty/leave phases record data but are not pass/failed live.
LONG_DWELL_ROOMS = {'cuddle cross'}

try:
    with open(os.path.join(REPO, 'sim', 'maze_layout.json')) as f:
        ROUTE = [r.lower() for r in json.load(f).get('route', [])]
except Exception:
    ROUTE = []


def _route_pos(room):
    try:
        return ROUTE.index(room.lower())
    except ValueError:
        return len(ROUTE)


def _slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def _utc():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _plain(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, 'value'):
        return value.value
    return str(value)


class NodeConn:
    """One node box: keepalive + entity mirror + tuning writes."""

    def __init__(self, room, host, port):
        self.room = room
        self.node_addr = f"{host}:{port}"
        if DIRECT:
            self.host, self.port = host, port
        else:
            self.host, self.port = '127.0.0.1', FORWARD_BASE + port
        self.client = None
        self.entities = {}       # key -> {'name','object_id','type','options'}
        self.entity_states = {}  # key -> {'state','at'}
        self.lock = asyncio.Lock()
        self._down_ticks = 0

    async def _connect(self):
        client = APIClient(self.host, self.port, password='')
        await client.connect(login=True)
        entities, _ = await client.list_entities_services()
        self.entities = {
            e.key: {'name': e.name,
                    'object_id': getattr(e, 'object_id', ''),
                    'type': type(e).__name__,
                    'options': list(getattr(e, 'options', []) or [])}
            for e in entities}
        client.subscribe_states(self._on_state)
        self.client = client
        logger.info(f"Node connected: {self.room} ({self.node_addr})")

    def _on_state(self, state):
        key = getattr(state, 'key', None)
        if key is None:
            return
        value = getattr(state, 'state', None)
        if getattr(state, 'missing_state', False):
            value = None
        self.entity_states[key] = {'state': value, 'at': time.time()}

    async def _drop(self):
        client, self.client = self.client, None
        self.entities = {}
        self.entity_states = {}
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass

    async def maintain(self):
        while True:
            try:
                async with self.lock:
                    if self.client is None:
                        try:
                            await asyncio.wait_for(self._connect(), CONNECT_TIMEOUT)
                        except Exception as e:
                            await self._drop()
                            logger.debug(f"{self.room} connect failed: {e}")
                    else:
                        try:
                            await asyncio.wait_for(self.client.device_info(),
                                                   PROBE_TIMEOUT)
                        except Exception as e:
                            await self._drop()
                            logger.info(f"Node lost: {self.room} "
                                        f"({type(e).__name__})")
            except Exception as e:
                logger.error(f"keepalive [{self.room}]: {e}", exc_info=True)
            if self.client is None:
                self._down_ticks = min(self._down_ticks + 1, 8)
                delay = min(KEEPALIVE_MAX_BACKOFF_S,
                            KEEPALIVE_TICK_S * (2 ** (self._down_ticks - 1)))
            else:
                self._down_ticks = 0
                delay = KEEPALIVE_TICK_S
            await asyncio.sleep(delay)

    async def write(self, key, value):
        info = self.entities.get(key)
        if info is None or self.client is None:
            return False
        kind = info['type']
        try:
            async with self.lock:
                # aioesphomeapi command methods are sync sends in some
                # versions, coroutines in others (same dance as the Pi
                # server's _run).
                if kind == 'NumberInfo':
                    result = self.client.number_command(key, float(value))
                elif kind == 'SelectInfo':
                    result = self.client.select_command(key, str(value))
                elif kind == 'SwitchInfo':
                    result = self.client.switch_command(
                        key, value in (True, 1, '1', 'true', 'True', 'on', 'ON'))
                else:
                    return False
                if inspect.isawaitable(result):
                    await result
            return True
        except Exception as e:
            logger.error(f"write [{self.room}] {info['name']}={value}: {e}")
            await self._drop()
            return False


class Capture:
    def __init__(self, path, room, label, note, entity_names):
        self.path = path
        self.label = label
        self.started = time.monotonic()
        self.file = open(path, 'a')
        self._write({'meta': {'room': room, 'label': label, 'note': note,
                              'started_utc': _utc(), 'entities': entity_names}})

    def _write(self, obj):
        self.file.write(json.dumps(obj) + '\n')
        self.file.flush()

    def sample(self, states):
        self._write({'t': round(time.monotonic() - self.started, 2), 's': states})

    def mark(self, text):
        self._write({'t': round(time.monotonic() - self.started, 2), 'mark': text})

    def close(self):
        try:
            self.file.close()
        except OSError:
            pass


nodes = {}       # room lower -> NodeConn
captures = {}    # room lower -> Capture
guided = {}      # room lower -> {'i','end','samples','task'}
verdicts = {}    # room lower -> last guided verdict dict
app = Quart(__name__)


def _conn(room):
    return nodes.get((room or '').lower())


def _journal(entry):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, 'tuning_log.jsonl'), 'a') as f:
        f.write(json.dumps(entry) + '\n')


def _entity_rows(conn):
    rows = []
    for key, info in list(conn.entities.items()):
        if info['type'] not in STATE_TYPES:
            continue
        st = conn.entity_states.get(key)
        rows.append({'key': key, 'name': info['name'],
                     'type': info['type'].replace('Info', ''),
                     'options': info.get('options') or [],
                     'state': _plain(st['state']) if st else None,
                     'age_s': round(time.time() - st['at'], 1) if st else None})
    order = {'BinarySensor': 0, 'Sensor': 1, 'TextSensor': 2, 'Number': 3,
             'Select': 4, 'Switch': 5}
    rows.sort(key=lambda r: (order.get(r['type'], 9), r['name']))
    return rows


def _sense_now(conn):
    """Current (presence, moving) booleans, or Nones while unknown/offline."""
    pres = mov = None
    for key, info in list(conn.entities.items()):
        n = info['name'].lower()
        if n.endswith('radar presence') or n.endswith('radar moving'):
            st = conn.entity_states.get(key)
            val = None if st is None else st['state']
            if n.endswith('radar presence'):
                pres = val
            else:
                mov = val
    return pres, mov


def _ordered_rooms():
    return sorted(nodes.values(), key=lambda c: (_route_pos(c.room), c.room))


def _next_room(room):
    ordered = [c.room for c in _ordered_rooms()]
    try:
        i = ordered.index(room)
    except ValueError:
        return None
    return ordered[i + 1] if i + 1 < len(ordered) else None


def _frac_on(vals):
    known = [v for v in vals if v is not None]
    if not known:
        return None
    return sum(1 for v in known if v) / len(known)


def _judge(room, samples):
    """samples: [(phase_id, presence, moving)] at SAMPLE_PERIOD_S. Plain words
    only — Tim reads this on a phone mid-maze. Trims cover walking time and the
    radar's own timeouts (5s module + 5s delayed_off standard)."""
    by = {}
    for pid, pres, mov in samples:
        by.setdefault(pid, []).append((pres, mov))
    if samples and sum(1 for _, p, _ in samples if p is None) > len(samples) * 0.3:
        return {'ok': False, 'utc': _utc(),
                'issues': ['node kept dropping off WiFi — redo this room']}
    issues = []
    long_dwell = room.lower() in LONG_DWELL_ROOMS
    if not long_dwell:
        f = _frac_on([p for p, _ in by.get('out', [])][-12:])       # last 6s
        if f is None or f > 0.25:
            issues.append('showed someone there while the room was EMPTY')
    f = _frac_on([p for p, _ in by.get('still', [])][10:])          # skip 5s
    if f is None or f < 0.75:
        issues.append('lost you while you stood STILL')
    mv = by.get('move', [])
    fp = _frac_on([p for p, _ in mv][6:])                           # skip 3s
    fm = _frac_on([m for _, m in mv][6:])
    if fp is None or fp < 0.75:
        issues.append('missed you while you WALKED around')
    elif fm is None or fm < 0.3:
        issues.append('saw you walking but not as "moving" — the entry trigger may not fire')
    if not long_dwell:
        f = _frac_on([p for p, _ in by.get('leave', [])][-12:])     # last 6s
        if f is None or f > 0.25:
            issues.append('still saw you AFTER you left — may be seeing into the next room')
    v = {'ok': not issues, 'issues': issues, 'utc': _utc()}
    if long_dwell:
        v['note'] = '60s dwell room — empty/leave phases recorded, not judged'
    return v


def _save_verdict(room, v):
    room_dir = os.path.join(DATA_DIR, _slug(room))
    os.makedirs(room_dir, exist_ok=True)
    with open(os.path.join(room_dir, 'verdict.json'), 'w') as f:
        json.dump(v, f)


async def _guided_task(conn, room_key):
    sess = guided[room_key]
    try:
        for i, (pid, _title, _sub, dur) in enumerate(GUIDED_STEPS):
            sess['i'] = i
            sess['end'] = time.monotonic() + dur
            cap = captures.get(room_key)
            if cap:
                cap.mark(f"STEP {pid}")
            while time.monotonic() < sess['end']:
                pres, mov = _sense_now(conn)
                if conn.client is None:
                    sess['samples'].append((pid, None, None))
                else:
                    sess['samples'].append((pid, bool(pres), bool(mov)))
                await asyncio.sleep(SAMPLE_PERIOD_S)
        v = _judge(conn.room, sess['samples'])
        cap = _stop_capture(conn)
        if cap:
            v['file'] = os.path.basename(cap.path)
        verdicts[room_key] = v
        _save_verdict(conn.room, v)
        logger.info(f"guided done: {conn.room} ok={v['ok']} issues={v['issues']}")
    except asyncio.CancelledError:
        _stop_capture(conn)
        raise
    except Exception as e:
        logger.error(f"guided [{conn.room}]: {e}", exc_info=True)
        _stop_capture(conn)
        verdicts[room_key] = {'ok': False, 'utc': _utc(),
                              'issues': ['test crashed on the server — redo']}
    finally:
        guided.pop(room_key, None)


async def _sampler(conn, room_key):
    try:
        while True:
            cap = captures.get(room_key)
            if cap is None:
                return
            if time.monotonic() - cap.started > MAX_CAPTURE_S:
                logger.info(f"capture auto-stop ({MAX_CAPTURE_S}s): {conn.room}")
                _stop_capture(conn)
                return
            states = {info['name']: _plain(conn.entity_states[key]['state'])
                      for key, info in list(conn.entities.items())
                      if info['type'] in STATE_TYPES and key in conn.entity_states}
            if not states and conn.client is None:
                states = {'_offline': True}
            cap.sample(states)
            await asyncio.sleep(SAMPLE_PERIOD_S)
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.error(f"sampler [{conn.room}]: {e}", exc_info=True)
        _stop_capture(conn)


def _stop_capture(conn):
    cap = captures.pop(conn.room.lower(), None)
    if cap is not None:
        cap.close()
    return cap


@app.route('/calibrate')
@app.route('/')
async def page():
    return await send_file(os.path.join(HERE, 'calibrate.html'))


@app.route('/api/calibration/rooms')
async def rooms():
    out = []
    for c in _ordered_rooms():
        rk = c.room.lower()
        pres, _ = _sense_now(c)
        v = verdicts.get(rk)
        out.append({'room': c.room, 'host': c.node_addr.split(':')[0],
                    'connected': c.client is not None,
                    'capturing': (captures[rk].label if rk in captures else False),
                    'guided': rk in guided,
                    'presence': None if pres is None else bool(pres),
                    'verdict': ({'ok': v['ok'], 'utc': v.get('utc')} if v else None)})
    return jsonify(out)


@app.route('/api/calibration/state')
async def state():
    conn = _conn(request.args.get('room', ''))
    if conn is None:
        return jsonify({'status': 'error', 'message': 'unknown room'}), 404
    rk = conn.room.lower()
    cap = captures.get(rk)
    sess = guided.get(rk)
    g = None
    if sess is not None:
        pid, title, sub, dur = GUIDED_STEPS[sess['i']]
        g = {'step': sess['i'] + 1, 'steps': len(GUIDED_STEPS),
             'id': pid, 'title': title, 'sub': sub, 'dur': dur,
             'remaining': max(0, round(sess['end'] - time.monotonic()))}
    return jsonify({'room': conn.room, 'host': conn.node_addr,
                    'connected': conn.client is not None,
                    'entities': _entity_rows(conn),
                    'guided': g,
                    'verdict': verdicts.get(rk),
                    'next_room': _next_room(conn.room),
                    'capture': ({'label': cap.label,
                                 'elapsed_s': round(time.monotonic() - cap.started, 1)}
                                if cap else None)})


@app.route('/api/calibration/write', methods=['POST'])
async def write():
    data = await request.get_json() or {}
    conn = _conn(data.get('room', ''))
    if conn is None:
        return jsonify({'status': 'error', 'message': 'unknown room'}), 404
    try:
        key, value = int(data['key']), data['value']
    except (KeyError, TypeError, ValueError):
        return jsonify({'status': 'error', 'message': 'need key + value'}), 400
    info = conn.entities.get(key) or {}
    ok = await conn.write(key, value)
    _journal({'utc': _utc(), 'room': conn.room,
              'entity': info.get('name', str(key)),
              'value': _plain(value), 'written': bool(ok)})
    cap = captures.get(conn.room.lower())
    if cap:
        cap.mark(f"SET {info.get('name', key)} = {value}"
                 + ('' if ok else ' (WRITE FAILED)'))
    if not ok:
        return jsonify({'status': 'error',
                        'message': 'write failed (node offline?)'}), 502
    return jsonify({'status': 'success'})


@app.route('/api/calibration/capture/start', methods=['POST'])
async def capture_start():
    data = await request.get_json() or {}
    conn = _conn(data.get('room', ''))
    if conn is None:
        return jsonify({'status': 'error', 'message': 'unknown room'}), 404
    room_key = conn.room.lower()
    if room_key in captures:
        return jsonify({'status': 'error', 'message': 'capture already running'}), 409
    label = (data.get('label') or 'unlabelled').strip() or 'unlabelled'
    cap = _begin_capture(conn, label, data.get('note') or '')
    return jsonify({'status': 'success', 'file': os.path.basename(cap.path),
                    'label': label})


def _begin_capture(conn, label, note):
    room_key = conn.room.lower()
    room_dir = os.path.join(DATA_DIR, _slug(conn.room))
    os.makedirs(room_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    path = os.path.join(room_dir, f"{stamp}_{_slug(label)}.jsonl")
    captures[room_key] = Capture(path, conn.room, label, note,
                                 sorted(i['name'] for i in conn.entities.values()))
    asyncio.get_event_loop().create_task(_sampler(conn, room_key))
    logger.info(f"capture started: {conn.room} '{label}' -> {path}")
    return captures[room_key]


@app.route('/api/calibration/guided/start', methods=['POST'])
async def guided_start():
    conn = _conn(((await request.get_json()) or {}).get('room', ''))
    if conn is None:
        return jsonify({'status': 'error', 'message': 'unknown room'}), 404
    room_key = conn.room.lower()
    if room_key in guided:
        return jsonify({'status': 'error', 'message': 'already running'}), 409
    if room_key in captures:
        return jsonify({'status': 'error',
                        'message': 'a manual capture is running — stop it in advanced'}), 409
    if conn.client is None:
        return jsonify({'status': 'error', 'message': 'node is offline'}), 502
    _begin_capture(conn, 'guided', '')
    sess = {'i': 0, 'end': time.monotonic() + GUIDED_STEPS[0][3], 'samples': []}
    guided[room_key] = sess
    sess['task'] = asyncio.get_event_loop().create_task(_guided_task(conn, room_key))
    logger.info(f"guided start: {conn.room}")
    return jsonify({'status': 'success'})


@app.route('/api/calibration/guided/cancel', methods=['POST'])
async def guided_cancel():
    conn = _conn(((await request.get_json()) or {}).get('room', ''))
    if conn is None:
        return jsonify({'status': 'error', 'message': 'unknown room'}), 404
    sess = guided.get(conn.room.lower())
    if sess is None:
        return jsonify({'status': 'error', 'message': 'not running'}), 409
    sess['task'].cancel()
    logger.info(f"guided cancelled: {conn.room}")
    return jsonify({'status': 'success'})


@app.route('/api/calibration/capture/stop', methods=['POST'])
async def capture_stop():
    conn = _conn((await request.get_json() or {}).get('room', ''))
    if conn is None:
        return jsonify({'status': 'error', 'message': 'unknown room'}), 404
    cap = _stop_capture(conn)
    if cap is None:
        return jsonify({'status': 'error', 'message': 'no capture running'}), 409
    logger.info(f"capture stopped: {conn.room}")
    return jsonify({'status': 'success', 'file': os.path.basename(cap.path)})


@app.route('/api/calibration/capture/mark', methods=['POST'])
async def capture_mark():
    data = await request.get_json() or {}
    conn = _conn(data.get('room', ''))
    if conn is None:
        return jsonify({'status': 'error', 'message': 'unknown room'}), 404
    cap = captures.get(conn.room.lower())
    if cap is None:
        return jsonify({'status': 'error', 'message': 'no capture running'}), 409
    cap.mark((data.get('text') or 'mark').strip() or 'mark')
    return jsonify({'status': 'success'})


@app.route('/api/calibration/captures')
async def capture_list():
    out = []
    room = request.args.get('room')
    conn = _conn(room) if room else None
    dirs = ([_slug(conn.room)] if conn else
            (sorted(os.listdir(DATA_DIR)) if os.path.isdir(DATA_DIR) else []))
    for d in dirs:
        room_dir = os.path.join(DATA_DIR, d)
        if not os.path.isdir(room_dir):
            continue
        for f in sorted(os.listdir(room_dir)):
            if f.endswith('.jsonl'):
                try:
                    size = os.path.getsize(os.path.join(room_dir, f))
                except OSError:
                    size = 0
                out.append({'room_dir': d, 'file': f, 'bytes': size})
    return jsonify(out)


@app.before_serving
async def start_keepalives():
    with open(os.path.join(REPO, 'node_audio_config.json')) as f:
        config = json.load(f)
    for room, entry in config.get('rooms', {}).items():
        conn = NodeConn(room, entry['host'], entry.get('port', 6053))
        nodes[room.lower()] = conn
        asyncio.get_event_loop().create_task(conn.maintain())
        try:
            with open(os.path.join(DATA_DIR, _slug(room), 'verdict.json')) as vf:
                verdicts[room.lower()] = json.load(vf)
        except Exception:
            pass
    logger.info(f"calibrate server up on :{LISTEN_PORT} "
                f"({'direct' if DIRECT else 'via tunnel forwards'}), "
                f"{len(nodes)} rooms")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=LISTEN_PORT, debug=False)
