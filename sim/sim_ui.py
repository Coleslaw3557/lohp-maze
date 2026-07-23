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
import http.server
import json
import logging
import os
import sys
import threading
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
RPI_PROJ_PORT = int(os.environ.get('RPI_PROJ_PORT', '5002'))  # renderer theme ctl

# Floor-projection engines (projection_engine.py at the repo root): the
# ACTIVE theme is stepped in this process and streamed to the page over
# /sim/projection. Themes are shared state — the Floor button switches every
# tab (and matches what production would project). Inactive themes keep their
# world frozen and resume where they left off.
# Defensive import — without numpy the sim still runs, minus the floor feed.
if REPO_DIR not in sys.path:
    sys.path.append(REPO_DIR)
try:
    from projection_engine import THEMES
except Exception as e:  # noqa: BLE001 — any import failure just disables the feed
    THEMES = None
    logging.getLogger(__name__).warning(f"floor engine unavailable: {e}")

_shows = {}
_THEME_FILE = os.path.join(SIM_DIR, '.floor_theme')
_floor_theme = 'lava'
try:
    _saved_theme = open(_THEME_FILE).read().strip()
    if THEMES and _saved_theme in THEMES:
        _floor_theme = _saved_theme  # sim restarts keep the last floor show
except OSError:
    pass


def _get_show():
    if THEMES is None:
        return None
    if _floor_theme not in _shows:
        try:
            layout = _load_json(os.path.join(SIM_DIR, 'maze_layout.json'))
            if layout.get('projection'):
                _shows[_floor_theme] = THEMES[_floor_theme](layout)
        except Exception:
            logger.exception("floor engine init failed")
    return _shows.get(_floor_theme)


async def _forward_theme_to_pi(name):
    """Best-effort mirror of a theme switch to the Pi renderer's control
    port, so the Floor button drives the REAL projector too when the Pi is
    reachable. Hand-rolled HTTP like the /sim/rpi_status probe — no deps."""
    if not RPI_HOST or not RPI_PROJ_PORT:
        return
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(RPI_HOST, RPI_PROJ_PORT), timeout=1.5)
    except (OSError, asyncio.TimeoutError):
        logger.info(f"Pi renderer unreachable — projector unchanged (switch it "
                    f"with: curl -X POST http://{RPI_HOST}:{RPI_PROJ_PORT}/theme/{name})")
        return
    try:
        writer.write((f'POST /theme/{name} HTTP/1.0\r\nHost: {RPI_HOST}\r\n'
                      f'Content-Length: 0\r\n\r\n').encode())
        await writer.drain()
        status = await asyncio.wait_for(reader.readline(), timeout=1.5)
        if b' 200 ' in status or status.endswith(b' 200\r\n'):
            logger.info(f"Pi projector theme -> {name}")
        else:
            logger.warning(f"Pi renderer refused theme {name}: {status!r} "
                           f"(old renderer build? redeploy + restart lohp-projection)")
    except (OSError, asyncio.TimeoutError) as e:
        logger.warning(f"Pi renderer theme forward failed mid-request: {e}")
    finally:
        writer.close()


def _set_floor_theme(name):
    global _floor_theme
    if THEMES is None or name not in THEMES or name == _floor_theme:
        return
    was_active = (_shows.get(_floor_theme) or None) and _shows[_floor_theme].active
    _floor_theme = name
    show = _get_show()
    logger.info(f"floor projection theme -> {name}")
    if show is not None and was_active:
        show.cue('theme-switch')  # carry a running show across the swap
    try:
        with open(_THEME_FILE, 'w') as f:
            f.write(name)
    except OSError:
        pass
    asyncio.ensure_future(_forward_theme_to_pi(name))


# Bench stand-in for the Pi renderer's theme control (projection_renderer.py
# ThemeControl): same GET /theme + POST /theme/<name|next> protocol on the same
# port, driving _set_floor_theme — so main.py's /api/next_floor_theme relay
# (the orb's very-long-press) behaves identically against the bench sim and the
# playa Pi. 0 disables.
FLOOR_CTL_PORT = int(os.environ.get('FLOOR_CTL_PORT', '5002'))
_loop = None  # the sim-ui event loop, set by run(); the ctl thread marshals onto it


def _start_floor_ctl():
    if not FLOOR_CTL_PORT or THEMES is None:
        return

    class Handler(http.server.BaseHTTPRequestHandler):
        def _reply(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.rstrip('/') == '/theme':
                self._reply(200, {'theme': _floor_theme, 'themes': sorted(THEMES)})
            else:
                self._reply(404, {'error': 'try /theme'})

        def do_POST(self):
            path = self.path.rstrip('/')
            name = None
            if path.startswith('/theme/'):
                name = path.rsplit('/', 1)[-1]
            elif path == '/theme':
                try:
                    n = int(self.headers.get('Content-Length') or 0)
                    name = json.loads(self.rfile.read(n) or b'{}').get('theme')
                except (ValueError, json.JSONDecodeError):
                    name = None
            if name == 'next':
                themes = sorted(THEMES)
                name = themes[(themes.index(_floor_theme) + 1) % len(themes)]
            if name in THEMES and _loop is not None:
                _loop.call_soon_threadsafe(_set_floor_theme, name)
                self._reply(200, {'ok': True, 'theme': name})
            else:
                self._reply(400, {'error': f'unknown theme {name!r}',
                                  'themes': sorted(THEMES)})

        def log_message(self, *_):
            pass  # switches already log from _set_floor_theme

    try:
        httpd = http.server.ThreadingHTTPServer(('', FLOOR_CTL_PORT), Handler)
    except OSError as e:
        logger.warning(f"floor theme ctl :{FLOOR_CTL_PORT} unavailable ({e}) — "
                       f"the /api/next_floor_theme relay won't reach the sim")
        return
    threading.Thread(target=httpd.serve_forever, name='floor-ctl', daemon=True).start()
    logger.info(f"floor theme ctl on :{FLOOR_CTL_PORT} (bench stand-in for the Pi renderer)")


async def _floor_loop():
    if _get_show() is None:
        return
    prev = time.monotonic()
    while True:
        await asyncio.sleep(1 / 20)
        now = time.monotonic()
        show = _get_show()
        if show is not None:
            show.step(min(now - prev, 0.25))
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
    """Floor engine stream: hello (theme + grid + palette + textures), then
    state at ~15 fps with the scalar field base64'd. Receives {'track':
    [x, z] | null} (world meters, already radar-lagged by the page), {'cue':
    name}, and {'theme': name} back. Several tabs share one engine — the show
    (and its theme) is shared state, like the real deck. On a theme switch
    the loop notices the active engine changed and re-hellos with the new
    palette + artwork."""
    def hello(s):
        return json.dumps({'hello': {
            'theme': s.THEME,
            'grid': [s.gw, s.gh],
            'palette': s.palette_list(),
            'heat_step': 2,
            'textures': s.hello_patches(),
        }})

    show = _get_show()
    if show is None:
        await websocket.send(json.dumps({'error': 'floor engine unavailable'}))
        return
    conn = f"sim-{id(asyncio.current_task()) & 0xffff:x}"
    await websocket.send(hello(show))

    async def _rx():
        while True:
            msg = json.loads(await websocket.receive())
            cur = _get_show()
            tr = msg.get('track')
            if tr and cur is not None:
                cur.set_tracks([{'id': conn, 'x': float(tr[0]), 'z': float(tr[1])}])
            if msg.get('cue') and cur is not None:
                cur.cue(str(msg['cue'])[:48])
            if msg.get('theme'):
                _set_floor_theme(str(msg['theme']))

    rx = asyncio.ensure_future(_rx())
    seen = show.event_total
    try:
        while True:
            cur = _get_show()
            if cur is not None and cur is not show:
                show = cur
                await websocket.send(hello(show))
                seen = show.event_total
            st = show.state(drain_events=False)
            st['events'], seen = show.fresh_events(seen)
            st['heat'] = show.heat_b64() if show.fade > 0 else None
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
    global _loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _loop = loop
    cfg = HyperConfig()
    cfg.bind = [f'0.0.0.0:{PORT}']
    cfg.accesslog = None
    cfg.errorlog = '-'
    never = asyncio.Event()
    loop.create_task(_floor_loop())
    _start_floor_ctl()
    logger.info(f"Sim UI starting on http://0.0.0.0:{PORT}")
    try:
        loop.run_until_complete(serve(app, cfg, shutdown_trigger=never.wait))
    except Exception:
        logger.exception("Sim UI server crashed")
