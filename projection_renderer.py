#!/usr/bin/env python3
"""Fullscreen renderer for the Cuddle floor show — runs ON the server Pi,
painting the LS625X over HDMI by writing the KMS framebuffer (/dev/fb0)
directly. No SDL/EGL/GL anywhere in the chain: numpy in, scanout out —
the vc4 EGL stack on the 3B+ refused kmsdrm (2026-07-22) and a memmap'd
framebuffer is the more playa-robust path anyway.

    python projection_renderer.py --source demo             # phantom walkers
    python projection_renderer.py --theme jungle            # snakes in the undergrowth
    python projection_renderer.py --source esphome \
        --node 192.168.253.x [--api-key ...]                # real LD2450
    python projection_renderer.py --windowed                # desktop debug (pygame)

Same engine as the sim (projection_engine.py); only the track source and the
pixel sink differ. Runs OUTSIDE the docker container (needs /dev/fb0):
systemd unit tools/lohp-projection.service (which also unbinds fbcon so the
console doesn't draw over the show), venv /opt/lohp-projection-venv — both
installed by tools/rpi-projection-setup.sh.

demo: two phantom walkers wander the deck, biased toward stones so the
mischief mechanic fires as an attract loop. Presence never lapses, so the
show stays on — bench/attract behavior until the LD2450 exists.

esphome: UNTESTED until the LD2450 is wired into the cuddle node's UART1
(hardware day). Subscribes to the node's `target N x/y` sensors (mm, sensor
frame) and maps them through the tracker pose in maze_layout.json; flip axes
with --invert-x if the real mounting disagrees.
"""
import argparse
import http.server
import json
import math
import os
import random
import signal
import sys
import threading
import time

import numpy as np

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_DIR)
from projection_engine import THEMES  # noqa: E402


class DemoTracks:
    """Phantom walkers with waypoint goals, 60% of the time a live stone —
    guarantees the sink/rise choreography keeps happening unattended."""

    def __init__(self, layout, n=2, seed=7):
        self.rng = random.Random(seed)
        img = layout['projection']['image']
        cx, cz = img['center']
        self.bx = (cx - img['w'] / 2 + 0.3, cx + img['w'] / 2 - 0.3)
        self.bz = (cz - img['d'] / 2 + 0.3, cz + img['d'] / 2 - 0.3)
        self.walkers = [self._spawn(i) for i in range(n)]

    def _rand_pt(self):
        return (self.rng.uniform(*self.bx), self.rng.uniform(*self.bz))

    def _spawn(self, i):
        x, z = self._rand_pt()
        return {'id': f'demo{i}', 'x': x, 'z': z, 'goal': self._rand_pt(),
                'speed': self.rng.uniform(0.4, 0.8), 'pause': 0.0}

    def _new_goal(self, w, engine):
        # stone-seeking only applies to the lava theme; jungle walkers just
        # wander (which is what spooks the snakes)
        up = [s for s in getattr(engine, 'stones', []) if s.state == 'up']
        if up and self.rng.random() < 0.6:
            s = self.rng.choice(up)
            w['goal'] = (s.wx, s.wz)
        else:
            w['goal'] = self._rand_pt()
        w['speed'] = self.rng.uniform(0.4, 0.8)

    def tracks(self, dt, engine):
        out = []
        for w in self.walkers:
            if w['pause'] > 0:
                w['pause'] -= dt
            else:
                gx, gz = w['goal']
                dx, dz = gx - w['x'], gz - w['z']
                d = math.hypot(dx, dz)
                if d < 0.12:
                    w['pause'] = self.rng.uniform(1.5, 4.0)
                    self._new_goal(w, engine)
                else:
                    step = min(d, w['speed'] * dt)
                    w['x'] += dx / d * step
                    w['z'] += dz / d * step
            out.append({'id': w['id'], 'x': w['x'], 'z': w['z']})
        return out


class EsphomeTracks:
    """LD2450 targets from the cuddle node over the ESPHome native API.
    Runs aioesphomeapi in a background thread; tracks() returns the latest.
    UNTESTED until the sensor exists — see the module docstring."""

    def __init__(self, layout, node, api_key='', invert_x=False):
        t = layout['projection']['tracker']
        self.pos = t['pos']
        yaw = math.radians(t.get('yaw_deg', 0))
        self.rot = (math.sin(yaw), math.cos(yaw))
        self.invert = -1.0 if invert_x else 1.0
        self.node, self.api_key = node, api_key
        self._lock = threading.Lock()
        self._raw = {}    # entity key -> value (mm)
        self._names = {}  # entity key -> object_id
        threading.Thread(target=self._run, name='esphome-tracks', daemon=True).start()

    def _run(self):
        import asyncio
        import aioesphomeapi

        async def go():
            cli = aioesphomeapi.APIClient(self.node, 6053, None, noise_psk=self.api_key or None)
            await cli.connect(login=True)
            entities = (await cli.list_entities_services())[0]
            for e in entities:
                self._names[e.key] = getattr(e, 'object_id', '')

            def on_state(state):
                with self._lock:
                    self._raw[state.key] = getattr(state, 'state', None)

            cli.subscribe_states(on_state)
            while True:
                await asyncio.sleep(60)

        while True:
            try:
                asyncio.run(go())
            except Exception as e:
                print(f"esphome source: {e}; retrying in 5 s", file=sys.stderr)
                time.sleep(5)

    def tracks(self, dt, engine):
        out = []
        with self._lock:
            raw = {self._names.get(k, ''): v for k, v in self._raw.items()}
        for i in (1, 2, 3):
            x_mm = raw.get(f'target_{i}_x')
            y_mm = raw.get(f'target_{i}_y')
            if not x_mm and not y_mm:  # LD2450 reports 0,0 for absent targets
                continue
            lx = (x_mm or 0) / 1000.0 * self.invert
            ly = (y_mm or 0) / 1000.0
            sx, cy = self.rot
            out.append({'id': f'ld{i}',
                        'x': self.pos[0] + lx * cy + ly * sx,
                        'z': self.pos[1] - lx * sx + ly * cy})
        return out


class ThemeControl:
    """Tiny HTTP control channel so the running show can be switched live
    (all engines are prebuilt at startup; a switch is just a pointer swap):

        GET  /theme          -> {"theme": "lava", "themes": ["jungle","lava"]}
        POST /theme/jungle   -> switch (also accepts POST /theme {"theme": x})

    The sim's Floor button forwards here (sim_ui._set_floor_theme), and
    anything on the LAN can drive it:  curl -X POST http://<pi>:5002/theme/jungle
    """

    def __init__(self, port, current):
        self.current = current
        self._want = None
        self._lock = threading.Lock()
        ctl = self

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
                    self._reply(200, {'theme': ctl.current,
                                      'themes': sorted(THEMES)})
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
                if name in THEMES:
                    with ctl._lock:
                        ctl._want = name
                    self._reply(200, {'ok': True, 'theme': name})
                else:
                    self._reply(400, {'error': f'unknown theme {name!r}',
                                      'themes': sorted(THEMES)})

            def log_message(self, *_):
                pass  # keep journald quiet; switches print from the main loop

        self._httpd = http.server.ThreadingHTTPServer(('', port), Handler)
        threading.Thread(target=self._httpd.serve_forever,
                         name='theme-ctl', daemon=True).start()

    def take(self):
        """The pending switch request, once (None when there isn't one)."""
        with self._lock:
            want, self._want = self._want, None
        return want


class FbOutput:
    """Write the engine frame into /dev/fb0, integer-upscaling if the fb is
    larger than the grid. All color math happens at GRID resolution and the
    result is broadcast into a preallocated buffer — packing at full fb res
    cost ~59 ms/frame on the Pi 3B+ (2026-07-23). With the legacy display
    stack and framebuffer_width/height set to the grid size, k == 1 and the
    VideoCore scaler does the whole upscale for free (with smoothing).
    Handles 32 bpp (xRGB) and 16 bpp (RGB565)."""

    def __init__(self, dev='/dev/fb0', sys_base='/sys/class/graphics/fb0'):
        self.w, self.h = (int(v) for v in
                          open(os.path.join(sys_base, 'virtual_size')).read().split(','))
        self.bpp = int(open(os.path.join(sys_base, 'bits_per_pixel')).read())
        self.stride = int(open(os.path.join(sys_base, 'stride')).read())
        if self.bpp not in (16, 32):
            raise SystemExit(f"unsupported framebuffer depth {self.bpp} bpp")
        self.fb = np.memmap(dev, dtype=np.uint8, mode='r+',
                            shape=(self.h, self.stride))
        self.fb[:] = 0
        if self.bpp == 16:
            self.fb16 = self.fb.view(np.uint16).reshape(self.h, self.stride // 2)
        self._buf = None
        self._warned = False

    def size(self):
        return (self.w, self.h)

    def blit(self, rgb):
        gh, gw = rgb.shape[:2]
        k = max(1, min(self.w // gw, self.h // gh))
        uh, uw = gh * k, gw * k
        y0, x0 = (self.h - uh) // 2, (self.w - uw) // 2
        if (x0 or y0) and not self._warned:
            self._warned = True
            print(f"fb {self.w}x{self.h} is not an integer multiple of the "
                  f"{gw}x{gh} grid — image letterboxed {uw}x{uh}; set "
                  f"framebuffer_width/height (or --grid) to match", flush=True)
        if self.bpp == 16:
            v = (((rgb[..., 0].astype(np.uint16) >> 3) << 11)
                 | ((rgb[..., 1].astype(np.uint16) >> 2) << 5)
                 | (rgb[..., 2].astype(np.uint16) >> 3))
            if k > 1:
                if self._buf is None or self._buf.shape != (uh, uw):
                    self._buf = np.empty((uh, uw), np.uint16)
                self._buf.reshape(gh, k, gw, k)[:] = v[:, None, :, None]
                v = self._buf
            self.fb16[y0:y0 + uh, x0:x0 + uw] = v
        else:
            out = np.empty((gh, gw, 4), np.uint8)
            out[..., 0] = rgb[..., 2]  # framebuffer is B,G,R,X byte order
            out[..., 1] = rgb[..., 1]
            out[..., 2] = rgb[..., 0]
            out[..., 3] = 255
            if k > 1:
                if self._buf is None or self._buf.shape != (uh, uw, 4):
                    self._buf = np.empty((uh, uw, 4), np.uint8)
                self._buf.reshape(gh, k, gw, k, 4)[:] = out[:, None, :, None, :]
                out = self._buf
            self.fb[y0:y0 + uh, x0 * 4:(x0 + uw) * 4] = out.reshape(uh, uw * 4)

    def close(self):
        self.fb[:] = 0
        self.fb.flush()


class PygameOutput:
    """Desktop debug window (--windowed); never used on the Pi."""

    def __init__(self, gw, gh):
        import pygame
        self.pygame = pygame
        pygame.display.init()
        self.screen = pygame.display.set_mode((gw * 3, gh * 3))
        pygame.display.set_caption('floor show (debug)')

    def size(self):
        return self.screen.get_size()

    def blit(self, rgb):
        pg = self.pygame
        for ev in pg.event.get():
            if ev.type == pg.QUIT or (ev.type == pg.KEYDOWN and ev.key == pg.K_ESCAPE):
                raise KeyboardInterrupt
        surf = pg.surfarray.make_surface(rgb.swapaxes(0, 1))
        pg.transform.smoothscale(surf, self.screen.get_size(), self.screen)
        pg.display.flip()

    def close(self):
        self.pygame.quit()


def main():
    ap = argparse.ArgumentParser(description='Cuddle floor projection renderer')
    ap.add_argument('--theme', choices=sorted(THEMES), default='lava',
                    help='which floor show starts (lava = stepping stones, '
                         'jungle = snakes); switchable live '
                         'via the control port')
    ap.add_argument('--ctl-port', type=int, default=5002,
                    help='HTTP theme control port (GET/POST /theme); 0 disables')
    ap.add_argument('--source', choices=['demo', 'esphome'], default='demo')
    ap.add_argument('--node', default='', help='esphome: cuddle node host/IP')
    ap.add_argument('--api-key', default='', help='esphome: noise PSK if set')
    ap.add_argument('--invert-x', action='store_true')
    ap.add_argument('--fps', type=int, default=25)
    ap.add_argument('--grid', type=int, default=256)
    ap.add_argument('--windowed', action='store_true', help='debug on a desktop')
    args = ap.parse_args()

    layout = json.load(open(os.path.join(REPO_DIR, 'sim', 'maze_layout.json')))
    # every theme is built up front (a few seconds at startup) so a live
    # switch never stalls the render loop mid-show
    engines = {name: cls(layout, grid_w=args.grid) for name, cls in THEMES.items()}
    engine = engines[args.theme]
    ctl = ThemeControl(args.ctl_port, args.theme) if args.ctl_port else None
    if args.source == 'esphome':
        if not args.node:
            ap.error('--source esphome needs --node')
        source = EsphomeTracks(layout, args.node, args.api_key, args.invert_x)
    else:
        source = DemoTracks(layout)

    out = PygameOutput(engine.gw, engine.gh) if args.windowed else FbOutput()
    print(f"floor renderer [{args.theme}]: {out.size()[0]}x{out.size()[1]} "
          f"grid {engine.gw}x{engine.gh} source={args.source} fps<={args.fps} "
          f"ctl={'off' if not ctl else f':{args.ctl_port}/theme'}",
          flush=True)

    running = [True]
    signal.signal(signal.SIGTERM, lambda *_: running.__setitem__(0, False))
    interval = 1.0 / args.fps
    prev = time.monotonic()
    stat_t0, stat_n, stat_eng, stat_blit = prev, 0, 0.0, 0.0
    try:
        while running[0]:
            now = time.monotonic()
            dt = min(now - prev, 0.25)
            prev = now
            want = ctl.take() if ctl else None
            if want and engines[want] is not engine:
                if engine.active:
                    engines[want].cue('theme-switch')  # carry the running show
                engine = engines[want]
                ctl.current = want
                print(f"theme -> {want}", flush=True)
            engine.set_tracks(source.tracks(dt, engine))
            engine.step(dt)
            frame = engine.render()
            t_mid = time.monotonic()
            out.blit(frame)
            t_end = time.monotonic()
            stat_n += 1
            stat_eng += t_mid - now
            stat_blit += t_end - t_mid
            if t_end - stat_t0 >= 60.0:  # journal heartbeat: achieved rate
                print(f"fps {stat_n / (t_end - stat_t0):.1f} "
                      f"(engine {stat_eng / stat_n * 1000:.0f} ms, "
                      f"blit {stat_blit / stat_n * 1000:.0f} ms, "
                      f"theme {ctl.current if ctl else args.theme})", flush=True)
                stat_t0, stat_n, stat_eng, stat_blit = t_end, 0, 0.0, 0.0
            time.sleep(max(0.0, interval - (time.monotonic() - now)))
    except KeyboardInterrupt:
        pass
    finally:
        out.close()


if __name__ == '__main__':
    main()
