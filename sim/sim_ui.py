"""Sim web UI — serves the 3D maze page and streams DMX frames to it.

Runs a second Quart app on port 5001 inside the same process as the real
server (its own thread + event loop, so nothing in main.py changes):

    GET  /              the Three.js walkthrough page (sim/web/)
    GET  /sim/config    merged config: fixtures, maze geometry, sensor map
    GET  /sim/health    frame counter / uptime
    WS   /sim/dmx       raw 168-channel universe frames as JSON, ~30/s max

The browser talks to the *real* server directly for everything else:
REST on :5000 (triggers, themes, effects) and the unit-audio WebSocket
protocol on :8765 — the page is just another client unit as far as the
production code is concerned.
"""
import asyncio
import json
import logging
import os
import re
import time

from quart import Quart, jsonify, send_from_directory, websocket
from hypercorn.config import Config as HyperConfig
from hypercorn.asyncio import serve

import sim_state

logger = logging.getLogger(__name__)

SIM_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(SIM_DIR)
WEB_DIR = os.path.join(SIM_DIR, 'web')
PORT = int(os.environ.get('SIM_UI_PORT', '5001'))

app = Quart(__name__, static_folder=WEB_DIR, static_url_path='')


def _load_json(path):
    with open(path) as f:
        return json.load(f)


def _extract_triggers():
    """Flatten the three unit configs into one browser-friendly trigger list.

    URLs like http://${server_ip}:5000/api/run_effect become just the path;
    the browser re-targets them at location.hostname.
    """
    triggers = []
    piezo_settings = {"attempts_required": 3, "correct_answer_probability": 0.25}
    for unit in ('a', 'b', 'c'):
        path = os.path.join(REPO_DIR, 'client', f'config-unit-{unit}.json')
        try:
            cfg = _load_json(path)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Skipping {path}: {e}")
            continue
        piezo_settings = cfg.get('piezo_settings', piezo_settings)
        for t in cfg.get('triggers', []):
            action = t.get('action', {})
            url = action.get('url', '')
            m = re.search(r':5000(/.*)$', url)
            triggers.append({
                'unit': cfg.get('unit_name', f'unit-{unit}'),
                'name': t.get('name'),
                'type': t.get('type'),
                'room': action.get('data', {}).get('room'),
                'threshold': t.get('threshold'),
                'action': {
                    'method': action.get('method', 'POST'),
                    'path': m.group(1) if m else '/api/run_effect',
                    'data': action.get('data', {}),
                },
            })
    return triggers, piezo_settings


@app.route('/')
async def index():
    return await send_from_directory(WEB_DIR, 'index.html')


@app.route('/sim/config')
async def sim_config():
    light_config = _load_json(os.path.join(REPO_DIR, 'light_config.json'))
    layout = _load_json(os.path.join(SIM_DIR, 'maze_layout.json'))
    triggers, piezo_settings = _extract_triggers()
    return jsonify({
        'ports': {'api': 5000, 'audio_ws': 8765},
        'channels_per_fixture': 8,
        'num_channels': len(sim_state.latest_frame),
        'light_models': light_config['light_models'],
        'room_layout': light_config['room_layout'],
        'layout': layout,
        'triggers': triggers,
        'piezo_settings': piezo_settings,
    })


@app.route('/sim/health')
async def sim_health():
    return jsonify({
        'frame_seq': sim_state.frame_seq,
        'uptime_s': round(time.time() - sim_state.started_at, 1),
    })


@app.websocket('/sim/dmx')
async def dmx_feed():
    last_sent = -1
    while True:
        seq = sim_state.frame_seq
        if seq != last_sent:
            await websocket.send(json.dumps({
                'seq': seq,
                'ch': list(sim_state.latest_frame),
            }))
            last_sent = seq
        await asyncio.sleep(1 / 30)


def run():
    """Entry point for the sim-ui thread (non-main thread: no signal handlers)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    cfg = HyperConfig()
    cfg.bind = [f'0.0.0.0:{PORT}']
    cfg.accesslog = None
    cfg.errorlog = '-'
    never = asyncio.Event()
    logger.info(f"Sim UI starting on http://0.0.0.0:{PORT}")
    try:
        loop.run_until_complete(serve(app, cfg, shutdown_trigger=never.wait))
    except Exception:
        logger.exception("Sim UI server crashed")
