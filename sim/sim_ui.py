"""Sim web UI — serves the 3D maze page and streams DMX frames to it.

Runs a second Quart app on port 5001 inside the same process as the real
server (its own thread + event loop, so nothing in main.py changes):

    GET  /              the Three.js walkthrough page (sim/web/)
    GET  /sim/config    merged config: fixtures, maze geometry, sensor map
    GET  /sim/health    frame counter / uptime
    WS   /sim/dmx       raw universe frames (NUM_FIXTURES x 8 ch) as JSON, ~30/s max

The browser talks to the *real* server directly for everything else:
REST on :5000 (triggers, themes, effects) and the unit-audio WebSocket
protocol on :8765 — the page is just another client unit as far as the
production code is concerned.
"""
import asyncio
import json
import logging
import os
import sys
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
# Production server Pi watched by the header RPI dot (/sim/rpi_status).
# Default is the DietPi image's mDNS name; set RPI_HOST=<ip> once the real
# address is known, or RPI_HOST= (empty) to disable the probe.
RPI_HOST = os.environ.get('RPI_HOST', 'lohp-server.local')
RPI_API_PORT = 5000

# LAVA floor-projection engine (projection_engine.py at the repo root):
# stepped in this process, streamed to the page over /sim/projection.
# Defensive import — without numpy the sim still runs, minus the lava feed.
if REPO_DIR not in sys.path:
    sys.path.append(REPO_DIR)
try:
    from projection_engine import LavaShow, palette_lut
except Exception as e:  # noqa: BLE001 — any import failure just disables the feed
    LavaShow, palette_lut = None, None
    logging.getLogger(__name__).warning(f"lava engine unavailable: {e}")

_lava = None


def _get_lava():
    global _lava
    if _lava is None and LavaShow is not None:
        try:
            layout = _load_json(os.path.join(SIM_DIR, 'maze_layout.json'))
            if layout.get('projection'):
                _lava = LavaShow(layout)
        except Exception:
            logger.exception("lava engine init failed")
    return _lava


async def _lava_loop():
    lava = _get_lava()
    if lava is None:
        return
    prev = time.monotonic()
    while True:
        await asyncio.sleep(1 / 20)
        now = time.monotonic()
        lava.step(min(now - prev, 0.25))
        prev = now

app = Quart(__name__, static_folder=WEB_DIR, static_url_path='')
# dev server: make browsers revalidate statics on refresh (304s are cheap on a
# LAN) instead of Quart's 12h max-age — otherwise app.js/backdrop edits don't
# show up on reload for anyone who had the page open in the last half-day
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0


def _load_json(path):
    with open(path) as f:
        return json.load(f)


def _extract_triggers():
    """Load the canonical trigger map (triggers.json at the repo root).

    Actions store bare paths (`/api/run_effect`, ...) that the browser
    re-targets at location.hostname. Promoted 2026-07-20 from the retired
    client/config-unit-*.json unit configs.
    """
    defaults = {"attempts_required": 3, "correct_answer_probability": 0.25}
    try:
        cfg = _load_json(os.path.join(REPO_DIR, 'triggers.json'))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f"triggers.json unreadable ({e}); trigger panel will be empty")
        return [], defaults
    return cfg.get('triggers', []), cfg.get('piezo_settings') or defaults


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
        'rpi': {'host': RPI_HOST, 'api_port': RPI_API_PORT},
        'channels_per_fixture': 8,
        'num_channels': len(sim_state.latest_frame),
        'light_models': light_config['light_models'],
        'room_layout': light_config['room_layout'],
        'layout': layout,
        'triggers': triggers,
        'piezo_settings': piezo_settings,
    })


@app.route('/cad/<path:filename>')
async def cad_item(filename):
    """Real cut files (cad-items/ at the repo root) — the beacon tiki faces
    load from here so the sim always renders the same SVGs the laser cuts."""
    return await send_from_directory(os.path.join(REPO_DIR, 'cad-items'), filename)


@app.route('/sim/health')
async def sim_health():
    return jsonify({
        'frame_seq': sim_state.frame_seq,
        'uptime_s': round(time.time() - sim_state.started_at, 1),
    })


@app.route('/sim/rpi_status')
async def rpi_status():
    """Probe the production server Pi. Three states so the sim can show
    booted-but-not-deployed (host_up) separately from absent (down):
    server_up = /api/health answered 200, host_up = TCP refused (box on the
    network, nothing bound on :5000), down = timeout / no such host."""
    if not RPI_HOST:
        return jsonify({'state': 'disabled', 'host': ''})
    t0 = time.monotonic()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(RPI_HOST, RPI_API_PORT), timeout=1.5)
    except ConnectionRefusedError:
        return jsonify({'state': 'host_up', 'host': RPI_HOST})
    except (OSError, asyncio.TimeoutError):
        return jsonify({'state': 'down', 'host': RPI_HOST})
    try:
        writer.write(f'GET /api/health HTTP/1.0\r\nHost: {RPI_HOST}\r\n\r\n'.encode())
        await writer.drain()
        status_line = await asyncio.wait_for(reader.readline(), timeout=1.5)
        parts = status_line.split()
        up = len(parts) >= 2 and parts[1] == b'200'
    except (OSError, asyncio.TimeoutError):
        up = False
    finally:
        writer.close()
    return jsonify({'state': 'server_up' if up else 'host_up',
                    'host': RPI_HOST,
                    'latency_ms': round((time.monotonic() - t0) * 1000)})


@app.websocket('/sim/projection')
async def projection_feed():
    """LAVA engine stream: hello (grid + palette), then state at ~15 fps with
    the heat field base64'd. Receives {'track': [x, z] | null} (world meters,
    already radar-lagged by the page) and {'cue': name} back. Several tabs
    share one engine — the show is shared state, like the real deck."""
    lava = _get_lava()
    if lava is None:
        await websocket.send(json.dumps({'error': 'lava engine unavailable'}))
        return
    conn = f"sim-{id(asyncio.current_task()) & 0xffff:x}"
    await websocket.send(json.dumps({'hello': {
        'grid': [lava.gw, lava.gh],
        'palette': palette_lut().tolist(),
        'heat_step': 2,
        'textures': lava.hello_patches(),
    }}))

    async def _rx():
        while True:
            msg = json.loads(await websocket.receive())
            tr = msg.get('track')
            if tr:
                lava.set_tracks([{'id': conn, 'x': float(tr[0]), 'z': float(tr[1])}])
            if msg.get('cue'):
                lava.cue(str(msg['cue'])[:48])

    rx = asyncio.ensure_future(_rx())
    seen = lava.event_total
    try:
        while True:
            st = lava.state(drain_events=False)
            st['events'], seen = lava.fresh_events(seen)
            st['heat'] = lava.heat_b64() if lava.fade > 0 else None
            await websocket.send(json.dumps(st))
            await asyncio.sleep(1 / 15)
    finally:
        rx.cancel()


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
    loop.create_task(_lava_loop())
    logger.info(f"Sim UI starting on http://0.0.0.0:{PORT}")
    try:
        loop.run_until_complete(serve(app, cfg, shutdown_trigger=never.wait))
    except Exception:
        logger.exception("Sim UI server crashed")
