"""SQLite event store for maze sensor telemetry and derived analytics.

Raw events are the source of truth. Higher-level room visits and maze runs are
derived from those rows so the inference rules can improve without rewriting
history.
"""
import csv
import io
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from statistics import median


SCHEMA_VERSION = 1


def utc_now():
    return datetime.now(timezone.utc)


def iso_utc(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def parse_time(value):
    if value is None or value == '':
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _json_dumps(value):
    if value is None:
        return None
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'))
    except (TypeError, ValueError):
        return json.dumps({'repr': repr(value)}, sort_keys=True, separators=(',', ':'))


def _json_loads(value):
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


class TelemetryStore:
    def __init__(self, path='data/telemetry.sqlite3'):
        self.path = path
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self._lock, self._conn:
            self._conn.execute('PRAGMA journal_mode=WAL')
            # WAL + NORMAL: no fsync per commit (only at checkpoints) —
            # FULL was fsyncing the SD card on every sensor event, on the
            # event loop, ahead of the response (live-night lag 2026-08-31).
            # A power cut can lose the tail of the WAL; fine for telemetry.
            self._conn.execute('PRAGMA synchronous=NORMAL')
            # Checkpoint often so the WAL stays small (the default 1000
            # pages let a ~4 MB WAL copy-back land inside a request).
            self._conn.execute('PRAGMA wal_autocheckpoint=200')
            self._conn.execute('PRAGMA foreign_keys=ON')
            self._conn.execute('PRAGMA user_version=%d' % SCHEMA_VERSION)
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS sensor_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_utc TEXT NOT NULL,
                    ts_epoch REAL NOT NULL,
                    room TEXT,
                    node_name TEXT,
                    event_type TEXT NOT NULL,
                    sensor_type TEXT,
                    sensor_name TEXT,
                    effect_name TEXT,
                    value_json TEXT,
                    source_ip TEXT,
                    user_agent TEXT,
                    node_uptime_ms INTEGER,
                    seq INTEGER
                )
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sensor_events_time
                ON sensor_events(ts_epoch)
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sensor_events_room_time
                ON sensor_events(room, ts_epoch)
            """)
            self._conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sensor_events_type_time
                ON sensor_events(event_type, ts_epoch)
            """)

    def close(self):
        with self._lock:
            self._conn.close()

    def record_event(self, event_type, room=None, node_name=None, sensor_type=None,
                     sensor_name=None, effect_name=None, value=None,
                     source_ip=None, user_agent=None, node_uptime_ms=None, seq=None,
                     ts=None):
        dt = ts or utc_now()
        ts_epoch = dt.timestamp()
        ts_utc = iso_utc(dt)
        node_uptime_ms = self._int_or_none(node_uptime_ms)
        seq = self._int_or_none(seq)
        with self._lock, self._conn:
            cur = self._conn.execute("""
                INSERT INTO sensor_events (
                    ts_utc, ts_epoch, room, node_name, event_type, sensor_type,
                    sensor_name, effect_name, value_json, source_ip, user_agent,
                    node_uptime_ms, seq
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ts_utc, ts_epoch, room, node_name, event_type, sensor_type,
                sensor_name, effect_name, _json_dumps(value), source_ip,
                user_agent, node_uptime_ms, seq,
            ))
            return cur.lastrowid

    @staticmethod
    def _int_or_none(value):
        if value is None or value == '':
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def query_events(self, room=None, event_type=None, since=None, until=None,
                     limit=250, newest_first=True):
        where = []
        args = []
        since_epoch = parse_time(since)
        until_epoch = parse_time(until)
        if room:
            where.append('room = ?')
            args.append(room)
        if event_type:
            where.append('event_type = ?')
            args.append(event_type)
        if since_epoch is not None:
            where.append('ts_epoch >= ?')
            args.append(since_epoch)
        if until_epoch is not None:
            where.append('ts_epoch <= ?')
            args.append(until_epoch)
        direction = 'DESC' if newest_first else 'ASC'
        try:
            limit = max(1, min(5000, int(limit)))
        except (TypeError, ValueError):
            limit = 250
        sql = 'SELECT * FROM sensor_events'
        if where:
            sql += ' WHERE ' + ' AND '.join(where)
        sql += f' ORDER BY ts_epoch {direction}, id {direction} LIMIT ?'
        args.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def room_visits(self, since=None, until=None, now=None):
        events = self.query_events(
            event_type=None, since=since, until=until, limit=5000, newest_first=False)
        relevant = [e for e in events if e['event_type'] in ('room_entry', 'room_vacated')]
        open_by_room = {}
        visits = []
        now_epoch = now if now is not None else time.time()
        for event in relevant:
            room = event.get('room')
            if not room:
                continue
            if event['event_type'] == 'room_entry':
                open_by_room.setdefault(room, []).append(event)
            elif event['event_type'] == 'room_vacated':
                entries = open_by_room.get(room) or []
                if not entries:
                    continue
                start = entries.pop(0)
                visits.append(self._visit_from_pair(start, event))
        for room, entries in open_by_room.items():
            for start in entries:
                visits.append(self._visit_from_pair(start, None, now_epoch=now_epoch))
        return visits

    def room_dwell_summary(self, since=None, until=None):
        visits = self.room_visits(since=since, until=until)
        by_room = {}
        for visit in visits:
            entry = by_room.setdefault(visit['room'], {
                'room': visit['room'],
                'visits': 0,
                'closed_visits': 0,
                'open_visits': 0,
                'total_duration_s': 0.0,
                'avg_duration_s': None,
                'median_duration_s': None,
                'max_duration_s': None,
                '_durations': [],
            })
            entry['visits'] += 1
            if visit['open']:
                entry['open_visits'] += 1
            else:
                entry['closed_visits'] += 1
                d = visit['duration_s']
                entry['_durations'].append(d)
                entry['total_duration_s'] += d
        for entry in by_room.values():
            durations = entry.pop('_durations')
            if durations:
                entry['avg_duration_s'] = round(sum(durations) / len(durations), 3)
                entry['median_duration_s'] = round(median(durations), 3)
                entry['max_duration_s'] = round(max(durations), 3)
                entry['total_duration_s'] = round(entry['total_duration_s'], 3)
            else:
                entry['total_duration_s'] = 0.0
        return sorted(by_room.values(), key=lambda r: (-r['total_duration_s'], r['room']))

    def maze_runs(self, route, since=None, until=None, timeout_s=900):
        if not route:
            return []
        route_index = {room: i for i, room in enumerate(route)}
        end_index = len(route) - 1
        entries = [
            e for e in self.query_events(
                event_type='room_entry', since=since, until=until,
                limit=5000, newest_first=False)
            if e.get('room') in route_index
        ]
        runs = []
        active = []
        next_id = 1

        def finish_stale(before_ts):
            nonlocal active
            keep = []
            for run in active:
                if before_ts - run['last_seen_epoch'] > timeout_s:
                    runs.append(self._finish_run(run, completed=False))
                else:
                    keep.append(run)
            active = keep

        for event in entries:
            ts = event['ts_epoch']
            finish_stale(ts)
            room = event['room']
            idx = route_index[room]
            if idx == 0 or not active:
                run = {
                    'id': next_id,
                    'started_at': event['ts_utc'],
                    'start_epoch': ts,
                    'last_seen_at': event['ts_utc'],
                    'last_seen_epoch': ts,
                    'last_room': room,
                    'current_index': idx,
                    'rooms': [room],
                    'inferred_start': idx != 0,
                }
                next_id += 1
                active.append(run)
            else:
                candidates = [r for r in active if idx >= r['current_index']]
                if not candidates:
                    candidates = active
                run = max(candidates, key=lambda r: (r['current_index'], r['last_seen_epoch']))
                run['last_seen_at'] = event['ts_utc']
                run['last_seen_epoch'] = ts
                run['last_room'] = room
                run['current_index'] = max(run['current_index'], idx)
                run['rooms'].append(room)
            if idx >= end_index:
                runs.append(self._finish_run(run, completed=True, ended_event=event))
                active.remove(run)
        runs.extend(self._finish_run(run, completed=False) for run in active)
        return runs

    def events_csv(self, events):
        out = io.StringIO()
        fields = [
            'id', 'ts_utc', 'room', 'node_name', 'event_type', 'sensor_type',
            'sensor_name', 'effect_name', 'value_json', 'source_ip', 'user_agent',
            'node_uptime_ms', 'seq',
        ]
        writer = csv.DictWriter(out, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        for event in events:
            row = dict(event)
            row['value_json'] = _json_dumps(event.get('value'))
            writer.writerow(row)
        return out.getvalue()

    @staticmethod
    def _visit_from_pair(start, end, now_epoch=None):
        end_epoch = end['ts_epoch'] if end else now_epoch
        return {
            'room': start['room'],
            'entered_at': start['ts_utc'],
            'vacated_at': end['ts_utc'] if end else None,
            'duration_s': round(max(0.0, end_epoch - start['ts_epoch']), 3),
            'open': end is None,
            'entry_event_id': start['id'],
            'vacate_event_id': end['id'] if end else None,
        }

    @staticmethod
    def _finish_run(run, completed, ended_event=None):
        end_epoch = ended_event['ts_epoch'] if ended_event else run['last_seen_epoch']
        ended_at = ended_event['ts_utc'] if ended_event else run['last_seen_at']
        return {
            'id': run['id'],
            'started_at': run['started_at'],
            'ended_at': ended_at,
            'completed': completed,
            'duration_s': round(max(0.0, end_epoch - run['start_epoch']), 3),
            'last_room': run['last_room'],
            'rooms': run['rooms'],
            'room_count': len(run['rooms']),
            'inferred_start': run['inferred_start'],
            'confidence': 'low' if run['inferred_start'] else 'medium',
        }

    @staticmethod
    def _row_to_dict(row):
        data = dict(row)
        data['value'] = _json_loads(data.pop('value_json'))
        return data
