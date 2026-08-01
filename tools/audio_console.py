#!/usr/bin/env python3
"""Audio pool console — a small standalone web tool for the maze's sound pools.

Deliberately separate from the sim and from the show server: this is the page you
hand to whoever prepares sounds. It joins triggers.json (which sensor in which room
fires which effect) to audio_config.json (each effect's pool of files) and lets you
audition, upload, add, reweight and retire the files in every pool.

Every action plays ONE file drawn from its pool at run time (audio_manager.py),
so a pool of one is still a pool — this tool never pins a single file.

audio_config.json is written atomically, with the previous version kept as
audio_config.json.bak. A running show server can be told to re-read it without a
restart (POST /api/reload_audio_config), and the ESP32 node cue WAVs can be
regenerated from here too.

    python3 tools/audio_console.py                    # http://0.0.0.0:5055
    python3 tools/audio_console.py --port 8080 --server http://lohp-server.local:5000
"""
import argparse
import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from quart import Quart, jsonify, request, send_file, send_from_directory
from werkzeug.utils import secure_filename

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
AUDIO_DIR = REPO / 'audio_files'
CONFIG_PATH = REPO / 'audio_config.json'
TRIGGERS_PATH = REPO / 'triggers.json'
BIKE_ROOM_YAML = REPO / 'sim' / 'esphome' / 'rooms' / 'bike-lock.yaml'
LAYOUT_PATH = REPO / 'sim' / 'maze_layout.json'
WEB_DIR = Path(__file__).resolve().parent / 'audio_console_web'
RETIRED_DIR = AUDIO_DIR / 'rejected' / 'retired-by-console'
CUE_SCRIPT = REPO / 'sim' / 'esphome' / 'make_node_audio.py'

from room_answer_pools import (ANSWER_EFFECTS, ROOM_ANSWER_POOL_PREFIXES,
                               ROOM_BACKGROUND_POOLS, answer_pool_name,
                               background_pool_name)  # noqa: E402

PLAYABLE = {'.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac'}
# Left out of the library view: generated node cues, undelivered pack zips, retired files.
LIBRARY_SKIP = {'cues', 'codex-prepped', 'rejected'}
MAX_UPLOAD_BYTES = 64 * 1024 * 1024
# Triggers that POST a server route instead of naming an effect (main.py fires
# Lightning maze-wide for the camp sign's storm button).
EFFECT_BY_PATH = {'/api/sign_storm': 'Lightning'}
# Pools the FLOOR SHOW fires rather than a sensor (floor_show_manager.py): the
# Cuddle projection's own events pick these, so triggers.json has nothing to
# say about them — but they belong on the room's card, not in the no-trigger
# list. One entry per pool: (pool name, what sets it off).
FLOOR_POOLS = {
    'Cuddle Cross': [
        ('Cuddle-Lava-Bed', 'LAVA theme: looping bed while the show is up'),
        ('Cuddle-Lava-Ambient', 'LAVA theme: ambient one-shots on a random timer'),
        ('Cuddle-Lava-Hit', 'LAVA theme: a stone sinking, a bubble bursting'),
        ('Cuddle-Lava-Breach', 'LAVA theme: Kukulkan surfacing'),
        ('Cuddle-Jungle-Bed', 'JUNGLE theme: looping night-jungle bed'),
        ('Cuddle-Jungle-Ambient', 'JUNGLE theme: birdies/beasties on a random timer'),
        ('Cuddle-Temple-Bed', 'TEMPLE theme: looping altar-brazier bed'),
        ('Cuddle-Temple-Ambient', 'TEMPLE theme: wind/ravens on a random timer'),
        ('Cuddle-Water-Bed', 'WATER theme: looping drips bed'),
        ('Cuddle-Water-Ambient', 'WATER theme: drips/winter wind on a random timer'),
        ('Cuddle-Chamber-Bed', 'CHAMBER theme: looping mysterious-perc bed (one of 16)'),
        ('Cuddle-Chamber-Trap', 'CHAMBER theme: a trap door taking a step'),
    ],
}
# Pools fired once as a room's last visitor leaves (/api/room_vacated ->
# audio_config `room_leave_sounds`).
LEAVE_POOLS = {
    'Cop Dodge': [
        ('CopDodge-Leave', 'last visitor leaves the room'),
    ],
    'Sparkle Pony Room': [
        ('SparklePonyRoom-Leave', 'last visitor leaves the room'),
    ],
}
# Pools the ambient one-shot engine fires (maze_ambient_manager.py,
# audio_config `ambient_oneshots`) — same idea as FLOOR_POOLS: no trigger row
# names them, but they belong on the room's card.
AMBIENT_POOLS = {
    'Entrance': [
        ('Entrance-Ambient', 'ambient one-shot timer over the hallowloop bed'),
    ],
}
MAZE_AMBIENT_EFFECT = 'MazeAmbient'

# Actions that the runtime can fire even though no single trigger row names
# them directly. Keep these visible on the room cards so sound prep covers the
# whole behavior surface, not just the static sensor map.
GAME_POOLS = {
    'Vertical Moop March': [
        ('VerticalMoopMarch-RightAnswer', 'all 4 moop buttons within 60s'),
        ('VerticalMoopMarch-WrongAnswer', 'moop round times out after a partial set'),
    ],
    'Bike Lock Room': [
        ('BikeLockRoom', 'bike quiz solved'),
    ],
}
BACKTRACK_EFFECT = 'Backtrack'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('audio_console')

app = Quart(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_UPLOAD_BYTES
app.config['BODY_TIMEOUT'] = 300
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0   # no stale UI after an edit or a pull
SERVER_URL = 'http://localhost:5000'


# --- files on disk -------------------------------------------------------

def load_json(path):
    with open(path) as f:
        return json.load(f)


# audio_config.json is hand-maintained too, so writes match its house style:
# 4-space indent, real UTF-8 punctuation, and weight rows kept on one line.
_NUMBER_ARRAY = re.compile(r'\[\s*((?:-?\d+(?:\.\d+)?\s*,\s*)+-?\d+(?:\.\d+)?)\s*\]')


def format_config(config):
    text = json.dumps(config, indent=4, ensure_ascii=False)
    text = _NUMBER_ARRAY.sub(
        lambda m: '[' + ', '.join(n.strip() for n in m.group(1).split(',')) + ']', text)
    return text + '\n'


def save_config(config):
    """Atomic write, with the previous version kept one deep as .bak."""
    tmp = CONFIG_PATH.with_name(CONFIG_PATH.name + '.tmp')
    with open(tmp, 'w') as f:
        f.write(format_config(config))
    if CONFIG_PATH.exists():
        shutil.copy2(CONFIG_PATH, CONFIG_PATH.with_name(CONFIG_PATH.name + '.bak'))
    os.replace(tmp, CONFIG_PATH)
    logger.info("wrote %s", CONFIG_PATH)


def save_triggers(config):
    """Atomic write for triggers.json, with the previous version kept one deep."""
    tmp = TRIGGERS_PATH.with_name(TRIGGERS_PATH.name + '.tmp')
    with open(tmp, 'w') as f:
        json.dump(config, f, indent=2)
        f.write('\n')
    if TRIGGERS_PATH.exists():
        shutil.copy2(TRIGGERS_PATH, TRIGGERS_PATH.with_name(TRIGGERS_PATH.name + '.bak'))
    os.replace(tmp, TRIGGERS_PATH)
    logger.info("wrote %s", TRIGGERS_PATH)


def save_bike_room_answers(answers):
    """Mirror the static Bike Lock answer key into the room node substitutions."""
    if not BIKE_ROOM_YAML.exists():
        logger.warning("Bike room yaml not found: %s", BIKE_ROOM_YAML)
        return
    text = BIKE_ROOM_YAML.read_text()
    replacements = {
        'bike_q1_correct': answers.get(1),
        'bike_q2_correct': answers.get(2),
    }
    for key, value in replacements.items():
        if value not in {'true', 'false'}:
            continue
        line = f'  {key}: "{value}"'
        pattern = re.compile(rf'^\s+{re.escape(key)}:\s*".*"$', re.M)
        if pattern.search(text):
            text = pattern.sub(line, text)
        else:
            room_line = re.search(r'^\s+room:\s*".*"$', text, re.M)
            if not room_line:
                raise ValueError(f'could not find substitutions block in {BIKE_ROOM_YAML}')
            text = text[:room_line.end()] + '\n' + line + text[room_line.end():]

    tmp = BIKE_ROOM_YAML.with_name(BIKE_ROOM_YAML.name + '.tmp')
    tmp.write_text(text)
    shutil.copy2(BIKE_ROOM_YAML, BIKE_ROOM_YAML.with_name(BIKE_ROOM_YAML.name + '.bak'))
    os.replace(tmp, BIKE_ROOM_YAML)
    logger.info("wrote %s", BIKE_ROOM_YAML)


def rel_path(path):
    return str(Path(path).relative_to(AUDIO_DIR)).replace(os.sep, '/')


def safe_audio_path(rel):
    """Resolve a pool/library path to a real file inside audio_files/, or None."""
    if not rel:
        return None
    candidate = (AUDIO_DIR / rel).resolve()
    try:
        candidate.relative_to(AUDIO_DIR.resolve())
    except ValueError:
        return None       # ../ escape
    return candidate


def library_files():
    """Every playable file under audio_files/, minus the generated/archive dirs."""
    out = []
    for path in sorted(AUDIO_DIR.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in PLAYABLE:
            continue
        top = path.relative_to(AUDIO_DIR).parts[0]
        if top in LIBRARY_SKIP:
            continue
        out.append(rel_path(path))
    return out


_probe_cache = {}   # (path, mtime, size) -> duration in seconds


def _cache_key(path, rel):
    stat = path.stat()
    return (rel, stat.st_mtime_ns, stat.st_size), stat


def _probe(path):
    try:
        probe = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'csv=p=0', str(path)],
            capture_output=True, text=True, timeout=10)
        return round(float(probe.stdout.strip()), 1)
    except (OSError, ValueError, subprocess.SubprocessError):
        return 0.0        # no ffprobe, or an unreadable file — the UI shows a dash


def prefetch_durations(rels):
    """One ffprobe per uncached file, in parallel — serially this is an 11-second
    page load on the full library, and durations are what tell two takes apart."""
    todo = {}
    for rel in rels:
        path = safe_audio_path(rel)
        if path is None or not path.is_file():
            continue
        key, _ = _cache_key(path, rel)
        if key not in _probe_cache:
            todo[key] = path
    if not todo:
        return
    with ThreadPoolExecutor(max_workers=12) as pool:
        for key, duration in zip(todo, pool.map(_probe, todo.values())):
            _probe_cache[key] = duration


def file_info(rel):
    """Size and duration for one file; duration comes from the prefetched cache."""
    path = safe_audio_path(rel)
    if path is None or not path.is_file():
        return {'path': rel, 'name': os.path.basename(rel), 'exists': False,
                'size': 0, 'duration': None}
    key, stat = _cache_key(path, rel)
    return {'path': rel, 'name': os.path.basename(rel), 'exists': True,
            'size': stat.st_size, 'duration': _probe_cache.get(key) or None}


def unique_basename(name):
    """Filenames must be unique across audio_files/, ignoring the extension: play
    commands carry the bare basename (remote_host_manager.py strips the directory)
    and the ESP32 nodes' cue ids come from the stem (node_audio_manager.cue_id), so
    a collision would play the wrong clip. Uploads get a -2, -3 … suffix instead."""
    taken = {os.path.splitext(os.path.basename(p))[0].lower() for p in library_files()}
    stem, ext = os.path.splitext(name)
    candidate, n = name, 2
    while os.path.splitext(candidate)[0].lower() in taken:
        candidate = f"{stem}-{n}{ext}"
        n += 1
    return candidate


# --- the joined view -----------------------------------------------------

def action_kind(trigger):
    """How a person walking the maze sets this off."""
    return {'presence': 'entry', 'button': 'button', 'piezo': 'knock'}.get(
        trigger.get('type'), trigger.get('type', 'trigger'))


def bike_option(trigger):
    """True/False option represented by one Bike Lock Room button."""
    match = re.search(r'\b(true|false)$', trigger.get('name', ''), re.IGNORECASE)
    return match.group(1).lower() if match else None


def bike_answer_key(triggers):
    questions = {}
    for trigger in triggers:
        game = trigger.get('game') or {}
        if game.get('id') != 'bike':
            continue
        question = game.get('question')
        option = bike_option(trigger)
        if question is None or option not in {'true', 'false'}:
            continue
        entry = questions.setdefault(int(question), {'question': int(question), 'options': []})
        entry['options'].append({
            'value': option,
            'label': option.title(),
            'trigger': trigger.get('name'),
            'correct': bool(game.get('correct')),
        })
        if game.get('correct') is True:
            entry['correct'] = option

    out = []
    for question in sorted(questions):
        entry = questions[question]
        entry['options'].sort(key=lambda o: o['value'] != 'true')
        entry.setdefault('correct', None)
        out.append(entry)
    return {'room': 'Bike Lock Room', 'questions': out}


def trigger_pool_effect(trigger, fallback_effect):
    """The pool a trigger should be shown under in the sound-console UI.

    Some triggers are backed by room-game firmware: their static HTTP action is
    only a fallback/default, while the game script chooses CorrectAnswer or
    WrongAnswer at press time. For the Bike Lock Room, triggers.json already
    carries the answer key, so show each physical button under the pool it will
    actually use.
    """
    game = trigger.get('game') or {}
    if game.get('id') == 'bike' and isinstance(game.get('correct'), bool):
        base = 'CorrectAnswer' if game['correct'] else 'WrongAnswer'
        return answer_pool_name(trigger.get('room'), base) or base
    return fallback_effect


def trigger_label(trigger):
    game = trigger.get('game') or {}
    label = trigger.get('name')
    if game.get('id') == 'bike' and isinstance(game.get('correct'), bool):
        result = 'RIGHT' if game['correct'] else 'WRONG'
        return f"{label} ({result})"
    return label


def trigger_action_kind(trigger):
    game = trigger.get('game') or {}
    if game.get('id') == 'bike' and isinstance(game.get('correct'), bool):
        return 'right answer' if game['correct'] else 'wrong answer'
    return action_kind(trigger)


def route_rooms():
    try:
        return list(load_json(LAYOUT_PATH).get('route', []))
    except (OSError, ValueError):
        return []


def build_state():
    config = load_json(CONFIG_PATH)
    effects = config.get('effects', {})
    triggers_config = load_json(TRIGGERS_PATH)
    triggers = triggers_config.get('triggers', [])
    prefetch_durations(library_files()
                       + [f for cfg in effects.values() for f in cfg.get('audio_files', [])])

    # room -> effect -> the triggers that fire it
    by_room = {}
    used_by = {}
    for trigger in triggers:
        room = trigger.get('room')
        data = trigger.get('action', {}).get('data', {})
        path = trigger.get('action', {}).get('path', '')
        effect = trigger_pool_effect(trigger, data.get('effect_name') or EFFECT_BY_PATH.get(path))
        entry = by_room.setdefault(room, {}).setdefault(
            effect, {'effect': effect, 'kind': trigger_action_kind(trigger), 'triggers': [],
                     'route': path if not data.get('effect_name') else None})
        label = trigger_label(trigger)
        entry['triggers'].append(label)
        used_by.setdefault(effect, []).append({'room': room, 'trigger': label})

    for room, pools in FLOOR_POOLS.items():
        for name, label in pools:
            by_room.setdefault(room, {}).setdefault(
                name, {'effect': name, 'kind': 'floor show', 'triggers': [label],
                       'route': None})
            used_by.setdefault(name, []).append({'room': room, 'trigger': label})

    for room, pools in AMBIENT_POOLS.items():
        for name, label in pools:
            by_room.setdefault(room, {}).setdefault(
                name, {'effect': name, 'kind': 'ambient', 'triggers': [label],
                       'route': None})
            used_by.setdefault(name, []).append({'room': room, 'trigger': label})

    for room, pools in LEAVE_POOLS.items():
        for name, label in pools:
            by_room.setdefault(room, {}).setdefault(
                name, {'effect': name, 'kind': 'leave', 'triggers': [label],
                       'route': None})
            used_by.setdefault(name, []).append({'room': room, 'trigger': label})

    route = route_rooms()
    global_actions = []
    maze_ambient_label = 'random room, random timer (POST /api/ambient to audition)'
    used_by.setdefault(MAZE_AMBIENT_EFFECT, []).append(
        {'room': 'Maze-wide', 'trigger': maze_ambient_label})
    global_actions.append({
        'effect': MAZE_AMBIENT_EFFECT,
        'kind': 'ambient',
        'triggers': [maze_ambient_label],
        'route': None,
        'testable': False,
    })
    if route:
        label = 'going backwards through the route'
        used_by.setdefault(BACKTRACK_EFFECT, []).append({'room': 'Maze route', 'trigger': label})
        global_actions.append({
            'effect': BACKTRACK_EFFECT,
            'kind': 'route',
            'triggers': [label],
            'route': ' → '.join(route),
            'testable': False,
        })

    for room, pools in GAME_POOLS.items():
        for name, label in pools:
            by_room.setdefault(room, {}).setdefault(
                name, {'effect': name, 'kind': 'game complete', 'triggers': [label],
                       'route': None})
            used_by.setdefault(name, []).append({'room': room, 'trigger': label})

    for room in ROOM_ANSWER_POOL_PREFIXES:
        for base_effect, (_, label) in ANSWER_EFFECTS.items():
            name = answer_pool_name(room, base_effect)
            placeholder = f'{label} pool placeholder'
            by_room.setdefault(room, {}).setdefault(
                name, {'effect': name, 'kind': 'answer', 'triggers': [placeholder],
                       'route': None})
            used_by.setdefault(name, []).append({'room': room, 'trigger': placeholder})

    for room in ROOM_BACKGROUND_POOLS:
        name = background_pool_name(room)
        label = 'background sounds'
        by_room.setdefault(room, {}).setdefault(
            name, {'effect': name, 'kind': 'background', 'triggers': [label],
                   'route': None, 'testable': False})
        used_by.setdefault(name, []).append({'room': room, 'trigger': label})

    # Walk order from entrance to exit, then any non-route rooms the layout or
    # triggers know about (for example Camp Sign).
    room_order = route
    try:
        layout_rooms = list(load_json(LAYOUT_PATH).get('rooms', {}).keys())
    except (OSError, ValueError):
        layout_rooms = []
    room_order += [r for r in layout_rooms if r not in room_order]
    room_order += [r for r in by_room if r not in room_order]

    def pool(name):
        cfg = effects.get(name, {})
        files = cfg.get('audio_files', [])
        weights = cfg.get('audio_weights') or []
        return {
            'name': name,
            'exists': name in effects,
            'comment': cfg.get('_comment'),
            'volume': cfg.get('volume', config.get('default_volume', 0.7)),
            'weighted': bool(cfg.get('audio_weights')),
            'files': [dict(file_info(f), weight=weights[i] if i < len(weights) else 1)
                      for i, f in enumerate(files)],
            'used_by': used_by.get(name, []),
        }

    rooms = []
    for room in room_order:
        actions = []
        for effect, meta in by_room.get(room, {}).items():
            actions.append(dict(meta, pool=pool(effect),
                                shared=len({u['room'] for u in used_by.get(effect, [])}) > 1))
        actions.sort(key=lambda a: (a['kind'] != 'entry', a['triggers'][0]))
        games = {}
        if room == 'Bike Lock Room':
            games['bike'] = bike_answer_key(triggers)
        rooms.append({'room': room, 'actions': actions, 'games': games})

    for action in global_actions:
        action['pool'] = pool(action['effect'])
        action['shared'] = False

    orphans = [pool(name) for name in effects if name not in used_by]
    in_pools = {f for cfg in effects.values() for f in cfg.get('audio_files', [])}
    library = [dict(file_info(rel), pools=sorted(n for n, c in effects.items()
                                                 if rel in c.get('audio_files', [])))
               for rel in library_files()]

    background_pools = [
        {'room': room, 'name': background_pool_name(room)}
        for room in room_order
        if background_pool_name(room) in effects
    ]

    return {
        'global_actions': global_actions,
        'rooms': rooms,
        'orphan_pools': orphans,
        'library': library,
        'unused_count': sum(1 for f in library if not f['pools']),
        'pool_names': sorted(effects),
        'background_pools': background_pools,
        'default_volume': config.get('default_volume', 0.7),
        'server': server_status(),
        'in_pools': len(in_pools),
    }


# --- the show server -----------------------------------------------------

def _push_config_to_server():
    """Best-effort: tell the running show server to re-read audio_config.json.
    Called after every pool edit so a removed sound stops playing NOW — not
    after someone remembers the apply button. Failure only logs: the console
    must keep editing even with the maze down."""
    try:
        status, _ = server_call('/api/reload_audio_config', {})
        if status != 200:
            logger.warning(f"show server config reload after edit: HTTP {status}")
    except Exception as e:
        logger.warning(f"show server config reload after edit failed ({e}) — "
                       "the maze plays its old pools until it reloads")


def push_config_to_server_soon():
    """Fire-and-forget reload off the request path."""
    asyncio.ensure_future(asyncio.to_thread(_push_config_to_server))


def server_call(path, payload=None, timeout=3.0):
    url = SERVER_URL.rstrip('/') + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method='POST' if data is not None else 'GET',
        headers={'Content-Type': 'application/json'} if data is not None else {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode()
    try:
        return resp.status, json.loads(body)
    except ValueError:
        return resp.status, {'message': body[:200]}


def server_status():
    try:
        status, _ = server_call('/api/health', timeout=0.8)
        return {'online': status == 200, 'url': SERVER_URL}
    except Exception:
        return {'online': False, 'url': SERVER_URL}


# --- API -----------------------------------------------------------------

@app.route('/api/state')
async def api_state():
    return jsonify(build_state())


@app.route('/api/games/bike', methods=['PUT'])
async def api_save_bike_answers():
    """Update the Bike Lock Room true/false answer key in triggers.json."""
    body = await request.json or {}
    answers = body.get('answers') or {}
    normalized = {}
    for question, answer in answers.items():
        try:
            q = int(question)
        except (TypeError, ValueError):
            return jsonify({'status': 'error', 'message': f'bad question: {question}'}), 400
        value = str(answer).lower()
        if value not in {'true', 'false'}:
            return jsonify({'status': 'error',
                            'message': f'question {q}: answer must be true or false'}), 400
        normalized[q] = value

    if not normalized:
        return jsonify({'status': 'error', 'message': 'no bike answers supplied'}), 400

    config = load_json(TRIGGERS_PATH)
    found = {q: set() for q in normalized}
    changed = False
    for trigger in config.get('triggers', []):
        game = trigger.get('game') or {}
        if game.get('id') != 'bike':
            continue
        question = game.get('question')
        option = bike_option(trigger)
        if question in normalized and option in {'true', 'false'}:
            correct = option == normalized[question]
            if game.get('correct') is not correct:
                game['correct'] = correct
                changed = True
            found[question].add(option)

    missing = [q for q, options in found.items() if options != {'true', 'false'}]
    if missing:
        return jsonify({'status': 'error',
                        'message': f'missing true/false bike triggers for question(s): {missing}'}), 400

    if changed:
        save_triggers(config)
        save_bike_room_answers(normalized)
    return jsonify({'status': 'success', 'bike': bike_answer_key(config.get('triggers', []))})


@app.route('/api/pools/<name>', methods=['PUT'])
async def api_save_pool(name):
    """Replace one pool wholesale: file list (order = display order), per-file
    weights and the effect volume. One write, so a half-applied pool is impossible.

    `base` = the file list the page LOADED for this pool. A save whose base no
    longer matches the pool on disk is REFUSED (409): a second tab or device
    holding an older view must never write its stale list back — that is how
    files someone just removed used to come back from the dead."""
    body = await request.json
    config = load_json(CONFIG_PATH)
    effects = config.setdefault('effects', {})
    if name not in effects:
        return jsonify({'status': 'error', 'message': f'no pool named {name}'}), 404

    base = body.get('base')
    if base is not None and list(base) != list(effects[name].get('audio_files', [])):
        return jsonify({'status': 'error', 'message':
                        f'{name} changed since this page loaded it (another tab or device '
                        'saved in between) — refreshing to the current pool; redo the edit'}), 409

    paths, weights, seen = [], [], set()
    for item in body.get('files', []):
        rel = (item.get('path') or '').strip().lstrip('/')
        if rel in seen:
            return jsonify({'status': 'error',
                            'message': f'{os.path.basename(rel)} is already in this pool'}), 400
        target = safe_audio_path(rel)
        if target is None or not target.is_file():
            return jsonify({'status': 'error', 'message': f'no such file: {rel}'}), 400
        seen.add(rel)
        paths.append(rel)
        try:
            weight = int(item.get('weight', 1))
        except (TypeError, ValueError):
            weight = 1
        weights.append(max(1, min(99, weight)))

    entry = effects[name]
    entry['audio_files'] = paths
    # audio_manager treats a missing audio_weights as uniform; keep the file that
    # way rather than writing a row of identical numbers.
    if len(set(weights)) > 1:
        entry['audio_weights'] = weights
    else:
        entry.pop('audio_weights', None)
    if 'volume' in body:
        try:
            entry['volume'] = max(0.0, min(1.0, round(float(body['volume']), 2)))
        except (TypeError, ValueError):
            pass
    save_config(config)
    push_config_to_server_soon()
    return jsonify({'status': 'success', 'pool': name, 'files': len(paths)})


@app.route('/api/pools', methods=['POST'])
async def api_create_pool():
    """Start an empty pool for an effect that has no audio yet (a new button's
    effect, say). The lights for a new effect are still Python in effects/."""
    body = await request.json
    name = (body.get('name') or '').strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', name):
        return jsonify({'status': 'error',
                        'message': 'pool name: letters, digits, - and _ only'}), 400
    config = load_json(CONFIG_PATH)
    effects = config.setdefault('effects', {})
    if name in effects:
        return jsonify({'status': 'error', 'message': f'{name} already exists'}), 400
    effects[name] = {'audio_files': [], 'volume': config.get('default_volume', 0.7)}
    save_config(config)
    return jsonify({'status': 'success', 'pool': name})


@app.route('/api/upload', methods=['POST'])
async def api_upload():
    """Multipart upload. `pool` (optional) appends the file to that pool;
    `room` (optional) picks the folder it lands in."""
    files = await request.files
    form = await request.form
    pool_name = (form.get('pool') or '').strip()
    room = (form.get('room') or '').strip()

    config = load_json(CONFIG_PATH)
    effects = config.setdefault('effects', {})
    if pool_name and pool_name not in effects:
        return jsonify({'status': 'error', 'message': f'no pool named {pool_name}'}), 404

    if room:
        dest_dir = AUDIO_DIR / 'rooms' / room / 'uploads'
    elif pool_name:
        dest_dir = AUDIO_DIR / 'uploads' / pool_name
    else:
        dest_dir = AUDIO_DIR / 'uploads'

    saved, renamed, skipped = [], [], []
    for storage in files.getlist('file'):
        original = os.path.basename(storage.filename or '')
        if os.path.splitext(original)[1].lower() not in PLAYABLE:
            skipped.append(f'{original} (not an audio file)')
            continue
        dest_dir.mkdir(parents=True, exist_ok=True)   # only once something lands
        clean = secure_filename(original) or 'upload.mp3'
        final = unique_basename(clean)
        if final != original:
            renamed.append(f'{original} -> {final}')
        await storage.save(str(dest_dir / final))   # Quart's FileStorage.save is async
        rel = rel_path(dest_dir / final)
        saved.append(rel)
        if pool_name:
            pool_files = effects[pool_name].setdefault('audio_files', [])
            if rel not in pool_files:
                pool_files.append(rel)
                if effects[pool_name].get('audio_weights'):
                    effects[pool_name]['audio_weights'].append(1)

    if not saved:
        return jsonify({'status': 'error', 'message': '; '.join(skipped) or 'no files'}), 400
    if pool_name:
        save_config(config)
        push_config_to_server_soon()
    return jsonify({'status': 'success', 'saved': saved, 'renamed': renamed,
                    'skipped': skipped, 'pool': pool_name or None})


@app.route('/api/retire', methods=['POST'])
async def api_retire():
    """Pull a file out of every pool and move it under audio_files/rejected/ —
    the maze stops playing it, but nothing is deleted."""
    body = await request.json
    rel = (body.get('path') or '').strip().lstrip('/')
    source = safe_audio_path(rel)
    if source is None or not source.is_file():
        return jsonify({'status': 'error', 'message': f'no such file: {rel}'}), 400

    config = load_json(CONFIG_PATH)
    dropped = []
    for name, entry in config.get('effects', {}).items():
        pool_files = entry.get('audio_files', [])
        if rel not in pool_files:
            continue
        index = pool_files.index(rel)
        pool_files.pop(index)
        if entry.get('audio_weights'):
            entry['audio_weights'].pop(index)
            if len(set(entry['audio_weights'])) <= 1:
                entry.pop('audio_weights')
        dropped.append(name)

    dest = RETIRED_DIR / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest = dest.with_name(unique_basename(dest.name))
    shutil.move(str(source), str(dest))
    save_config(config)
    push_config_to_server_soon()
    return jsonify({'status': 'success', 'moved_to': str(dest.relative_to(AUDIO_DIR)),
                    'removed_from': dropped})


@app.route('/api/apply', methods=['POST'])
async def api_apply():
    """Push the edited config at the running maze: reload it on the show server
    and (optionally) rebuild the ESP32 node cue WAVs."""
    body = await request.json or {}
    result = {'reload': None, 'cues': None}

    try:
        status, payload = server_call('/api/reload_audio_config', {})
        result['reload'] = ('ok' if status == 200 else 'error',
                            payload.get('message', f'{payload.get("pools", "")}'))
    except urllib.error.HTTPError as e:
        result['reload'] = ('error', 'server has no /api/reload_audio_config — restart it'
                            if e.code == 404 else f'server said {e.code}')
    except Exception as e:
        result['reload'] = ('error', f'server unreachable at {SERVER_URL} ({e})')

    if body.get('cues'):
        try:
            done = subprocess.run([sys.executable, str(CUE_SCRIPT)],
                                  capture_output=True, text=True, timeout=600)
            tail = (done.stdout or done.stderr or '').strip().splitlines()
            result['cues'] = ('ok' if done.returncode == 0 else 'error',
                              tail[-1] if tail else f'exit {done.returncode}')
        except Exception as e:
            result['cues'] = ('error', str(e))
    return jsonify({'status': 'success', 'result': result})


@app.route('/api/play_in_room', methods=['POST'])
async def api_play_in_room():
    """Fire the real effect (lights and sound) in the real room, through the show
    server — the same call the room's sensor makes."""
    body = await request.json
    try:
        status, payload = server_call(
            '/api/run_effect',
            {'effect_name': body.get('effect'), 'room': body.get('room')}, timeout=60)
        return jsonify({'status': 'success' if status == 200 else 'error',
                        'message': payload.get('message', '')}), status
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'{SERVER_URL}: {e}'}), 502


# --- static --------------------------------------------------------------

@app.route('/audio/<path:rel>')
async def serve_audio(rel):
    if safe_audio_path(rel) is None:
        return jsonify({'status': 'error', 'message': 'bad path'}), 400
    return await send_from_directory(str(AUDIO_DIR), rel)


@app.route('/')
async def index():
    return await send_file(str(WEB_DIR / 'index.html'))


@app.route('/<path:asset>')
async def static_asset(asset):
    return await send_from_directory(str(WEB_DIR), asset)


def main():
    global SERVER_URL
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--port', type=int, default=5055)
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--server', default='http://localhost:5000',
                        help='the show server, for reload/test-in-room (default %(default)s)')
    args = parser.parse_args()
    SERVER_URL = args.server

    print(f"Audio pool console on http://{args.host}:{args.port}  (show server: {SERVER_URL})")
    app.run(host=args.host, port=args.port, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
