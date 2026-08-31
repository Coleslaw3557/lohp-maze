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
    return jsonify([{'room': c.room, 'host': c.node_addr.split(':')[0],
                     'connected': c.client is not None,
                     'capturing': (captures[c.room.lower()].label
                                   if c.room.lower() in captures else False)}
                    for c in sorted(nodes.values(), key=lambda c: c.room)])


@app.route('/api/calibration/state')
async def state():
    conn = _conn(request.args.get('room', ''))
    if conn is None:
        return jsonify({'status': 'error', 'message': 'unknown room'}), 404
    cap = captures.get(conn.room.lower())
    return jsonify({'room': conn.room, 'host': conn.node_addr,
                    'connected': conn.client is not None,
                    'entities': _entity_rows(conn),
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
    room_dir = os.path.join(DATA_DIR, _slug(conn.room))
    os.makedirs(room_dir, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    path = os.path.join(room_dir, f"{stamp}_{_slug(label)}.jsonl")
    captures[room_key] = Capture(path, conn.room, label, data.get('note') or '',
                                 sorted(i['name'] for i in conn.entities.values()))
    asyncio.get_event_loop().create_task(_sampler(conn, room_key))
    logger.info(f"capture started: {conn.room} '{label}' -> {path}")
    return jsonify({'status': 'success', 'file': os.path.basename(path),
                    'label': label})


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
    logger.info(f"calibrate server up on :{LISTEN_PORT} "
                f"({'direct' if DIRECT else 'via tunnel forwards'}), "
                f"{len(nodes)} rooms")


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=LISTEN_PORT, debug=False)
