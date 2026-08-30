"""Field calibration of the room nodes' presence sensors from a phone.

GET /calibrate (frontend/calibrate.html) is a self-contained mobile page the
Pi serves on the maze LAN; it exists for on-playa bring-up (2026-08-30): walk
a room with the phone, watch the radar respond live, tune it, and record
labelled walk-tests for offline threshold analysis.

It rides the node-audio native-API connections — node_audio_manager keeps one
per box and its _NodeConn now mirrors entity info + every pushed state — so
calibration adds NO second API client per node.

Three jobs:

* live state: every binary_sensor / sensor / number / select / switch /
  text_sensor the node exposes, straight from the _NodeConn mirror (LD2410
  presence/moving + gate numbers, LD2450 zones/targets, ToF range).

* tuning writes: number/select/switch entities set live over the API. Every
  write lands in data/calibration/tuning_log.jsonl — the record of what was
  tried and settled on. The node's on_boot re-programs the module from YAML
  substitutions, so live tuning DIES WITH A NODE REBOOT until the settled
  values are baked into the room YAML and reflashed (that later pass reads
  this journal).

* captures: labelled recordings ("empty", "back wall", ...) sampling the
  entity mirror at 2 Hz to data/calibration/<room>/<ts>_<label>.jsonl, with
  tap-to-mark event lines.

data/calibration/ sits inside data/ so deploys never touch it
(tools/deploy-rpi.sh protects /data/***).
"""
import asyncio
import json
import logging
import os
import re
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SAMPLE_PERIOD_S = 0.5
MAX_CAPTURE_S = 900          # runaway guard: auto-stop after 15 min
# Entity types worth showing/recording; MediaPlayer stays audio's business.
STATE_TYPES = ('BinarySensorInfo', 'SensorInfo', 'NumberInfo', 'SelectInfo',
               'SwitchInfo', 'TextSensorInfo')


def _slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def _utc():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _plain(value):
    """JSON-safe entity state (aioesphomeapi hands enums for some types)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, 'value'):
        return value.value
    return str(value)


class _Capture:
    def __init__(self, path, room, label, note, entities):
        self.path = path
        self.label = label
        self.started = time.monotonic()
        self.file = open(path, 'a')
        self._write({'meta': {'room': room, 'label': label, 'note': note,
                              'started_utc': _utc(),
                              'entities': sorted(e['name'] for e in entities)}})

    def _write(self, obj):
        self.file.write(json.dumps(obj) + '\n')
        self.file.flush()

    def sample(self, states):
        self._write({'t': round(time.monotonic() - self.started, 2),
                     's': states})

    def mark(self, text):
        self._write({'t': round(time.monotonic() - self.started, 2),
                     'mark': text})

    def close(self):
        try:
            self.file.close()
        except OSError:
            pass


class CalibrationManager:
    def __init__(self, node_audio_manager, data_dir=os.path.join('data', 'calibration')):
        self.node_audio = node_audio_manager
        self.data_dir = data_dir
        self.captures = {}        # room key (lower) -> _Capture
        self._sampler_tasks = {}  # room key -> asyncio.Task

    def _conn(self, room):
        return self.node_audio.rooms.get((room or '').lower())

    # --- live view ---

    def rooms(self):
        return [{'room': c.room, 'host': c.host,
                 'connected': c.client is not None,
                 'capturing': (c.room.lower() in self.captures
                               and self.captures[c.room.lower()].label)}
                for c in sorted(self.node_audio.rooms.values(),
                                key=lambda c: c.room)]

    def _entity_rows(self, conn):
        rows = []
        for key, info in list(conn.entities.items()):
            if info['type'] not in STATE_TYPES:
                continue
            state = conn.entity_states.get(key)
            rows.append({
                'key': key,
                'name': info['name'],
                'type': info['type'].replace('Info', ''),
                'options': info.get('options') or [],
                'state': _plain(state['state']) if state else None,
                'age_s': round(time.time() - state['at'], 1) if state else None,
            })
        order = {'BinarySensor': 0, 'Sensor': 1, 'TextSensor': 2, 'Number': 3,
                 'Select': 4, 'Switch': 5}
        rows.sort(key=lambda r: (order.get(r['type'], 9), r['name']))
        return rows

    def state(self, room):
        conn = self._conn(room)
        if conn is None:
            return None
        cap = self.captures.get(conn.room.lower())
        return {'room': conn.room, 'host': conn.host,
                'connected': conn.client is not None,
                'entities': self._entity_rows(conn),
                'capture': ({'label': cap.label,
                             'elapsed_s': round(time.monotonic() - cap.started, 1)}
                            if cap else None)}

    # --- tuning writes ---

    async def write_entity(self, room, key, value):
        conn = self._conn(room)
        if conn is None:
            return None
        info = conn.entities.get(key)
        if info is None:
            return False
        kind = info['type']
        if kind == 'NumberInfo':
            ok = await conn.set_number(key, float(value))
        elif kind == 'SelectInfo':
            ok = await conn.set_select(key, str(value))
        elif kind == 'SwitchInfo':
            ok = await conn.set_switch(
                key, value in (True, 1, '1', 'true', 'True', 'on', 'ON'))
        else:
            return False
        self._journal({'utc': _utc(), 'room': conn.room, 'entity': info['name'],
                       'value': _plain(value), 'written': bool(ok)})
        cap = self.captures.get(conn.room.lower())
        if cap:
            cap.mark(f"SET {info['name']} = {value}"
                     + ('' if ok else ' (WRITE FAILED)'))
        return ok

    def _journal(self, entry):
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            with open(os.path.join(self.data_dir, 'tuning_log.jsonl'), 'a') as f:
                f.write(json.dumps(entry) + '\n')
        except OSError as e:
            logger.error(f"Calibration journal write failed: {e}")

    # --- captures ---

    def start_capture(self, room, label, note=''):
        conn = self._conn(room)
        if conn is None:
            return None
        room_key = conn.room.lower()
        if room_key in self.captures:
            return False
        label = (label or 'unlabelled').strip() or 'unlabelled'
        room_dir = os.path.join(self.data_dir, _slug(conn.room))
        os.makedirs(room_dir, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
        path = os.path.join(room_dir, f"{stamp}_{_slug(label)}.jsonl")
        self.captures[room_key] = _Capture(path, conn.room, label, note or '',
                                           self._entity_rows(conn))
        task = asyncio.create_task(self._sampler(conn, room_key))
        self._sampler_tasks[room_key] = task
        logger.info(f"Calibration capture started: {conn.room} '{label}' -> {path}")
        return {'file': os.path.basename(path), 'label': label}

    def stop_capture(self, room):
        conn = self._conn(room)
        if conn is None:
            return None
        room_key = conn.room.lower()
        cap = self.captures.pop(room_key, None)
        task = self._sampler_tasks.pop(room_key, None)
        if task is not None:
            task.cancel()
        if cap is None:
            return False
        cap.close()
        logger.info(f"Calibration capture stopped: {conn.room} "
                    f"({time.monotonic() - cap.started:.0f}s)")
        return {'file': os.path.basename(cap.path)}

    def mark(self, room, text):
        conn = self._conn(room)
        cap = self.captures.get(conn.room.lower()) if conn else None
        if cap is None:
            return None if conn is None else False
        cap.mark((text or 'mark').strip() or 'mark')
        return True

    async def _sampler(self, conn, room_key):
        try:
            while True:
                cap = self.captures.get(room_key)
                if cap is None:
                    return
                if time.monotonic() - cap.started > MAX_CAPTURE_S:
                    logger.info(f"Calibration capture auto-stopped "
                                f"({MAX_CAPTURE_S}s cap): {conn.room}")
                    self.stop_capture(conn.room)
                    return
                states = {info['name']: _plain(conn.entity_states[key]['state'])
                          for key, info in list(conn.entities.items())
                          if info['type'] in STATE_TYPES
                          and key in conn.entity_states}
                if not states and conn.client is None:
                    states = {'_offline': True}
                cap.sample(states)
                await asyncio.sleep(SAMPLE_PERIOD_S)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Calibration sampler [{conn.room}] died: {e}",
                         exc_info=True)
            self.stop_capture(conn.room)

    def list_captures(self, room=None):
        out = []
        if not os.path.isdir(self.data_dir):
            return out
        rooms = ([_slug(self._conn(room).room)] if room and self._conn(room)
                 else [d for d in sorted(os.listdir(self.data_dir))
                       if os.path.isdir(os.path.join(self.data_dir, d))])
        for d in rooms:
            room_dir = os.path.join(self.data_dir, d)
            if not os.path.isdir(room_dir):
                continue
            for f in sorted(os.listdir(room_dir)):
                if not f.endswith('.jsonl'):
                    continue
                path = os.path.join(room_dir, f)
                try:
                    size = os.path.getsize(path)
                except OSError:
                    size = 0
                out.append({'room_dir': d, 'file': f, 'bytes': size})
        return out
