"""Cuddle Cross floor projection — the LAVA show engine.

Stepping stones on molten lava (wiring-guides/cuddle-lava-plan.md): the deck
is a flowing heat field, ~8 basalt stepping stones ride on it, and tracked
walkers get played with — a stone someone is clearly walking toward sinks
while another rises off to the side of their path. Bubbles pop; lava recoils
in a glow ring around feet; the show cues on presence and fades out after
the configured timeout.

One engine, two displays: the sim streams state + heat field to the browser
(sim/sim_ui.py /sim/projection), production renders fullscreen to the LS625X
(projection_renderer.py). Pure numpy — no GUI deps. Inputs are tracked
positions in world meters (LD2450 or the sim avatar); callers drive time via
step(dt), so behavior is reproducible in tests.

Geometry (world->image mapping, deck-outline mask, mast island) is a port of
the sim preview's buildProjection (sim/web/app.js) against the same
maze_layout.json `projection` key — the two must agree or the sim lies.
"""
import base64
import math
import random

import numpy as np

# ---- tuning knobs (see the plan doc; all distances meters, times seconds) ----
STONE_N = 6                  # cap; the chain typically seats 5 + the spare
STONE_R_M = 0.19
STONE_MIN_SPACE_M = 0.55
CHAIN_SPACING_M = 0.62       # stride: center-to-center along the crossing
CHAIN_JITTER_M = 0.10
STONE_EDGE_MARGIN_M = 0.16
STONE_MIN_UP = 3             # mischief never drops the up-count below this
APPROACH_DOT = 0.68          # heading cone: cos(angle person->stone vs velocity)
APPROACH_NEAR_M = 0.35
APPROACH_FAR_M = 1.7
DWELL_S = 0.7                # how long a stone must stay "targeted" before it sinks
SINK_S = 1.3
RISE_S = 1.6
STONE_COOLDOWN_S = 8.0
GLOBAL_COOLDOWN_S = 3.0
WALK_SPEED_GATE = 0.15       # m/s; slower than this isn't "walking toward" anything
TRACK_VEL_EMA = 0.35
TRACK_STALE_S = 1.0          # drop tracks not updated for this long
BUBBLE_RATE_HZ = 0.6
BUBBLE_LIFE_S = (0.8, 1.4)
RECOIL_R_M = 0.35            # soft warm brightening around feet (no hard ring)
RECOIL_AMOUNT = 0.28
FADE_PER_S = 1.5

# blackbody-ish lava ramp
_PALETTE_STOPS = [
    (0.00, (5, 2, 2)),
    (0.35, (52, 8, 2)),
    (0.55, (122, 22, 2)),
    (0.72, (255, 90, 0)),
    (0.88, (255, 200, 48)),
    (1.00, (255, 244, 176)),
]
_STONE_CORE = np.array([128, 128, 132], np.float32)  # grey rock, cool tint
_STONE_EDGE = np.array([70, 70, 76], np.float32)
_STONE_HOT = np.array([255, 120, 20], np.float32)    # only while sinking/rising
_ISLAND_CORE = np.array([104, 94, 84], np.float32)   # the altar outcrop, browner
_ISLAND_EDGE = np.array([56, 50, 46], np.float32)
_AMBER = np.array([255, 196, 96], np.float32)        # glyph glint on approach
_CARVE_DARK = 0.36     # carved grooves multiply the rock color by this
GLINT_R_M = 0.55       # glyph starts glinting inside this walker distance
DAPPLE_STRENGTH = 0.20  # canopy shadow at the deck rim
EMBER_MAX = 14
EMBER_RATE_HZ = 1.1
EMBER_LIFE_S = (2.0, 4.0)


def palette_lut():
    lut = np.zeros((256, 3), np.uint8)
    for i in range(256):
        t = i / 255.0
        for (p0, c0), (p1, c1) in zip(_PALETTE_STOPS, _PALETTE_STOPS[1:]):
            if p0 <= t <= p1:
                f = (t - p0) / ((p1 - p0) or 1.0)
                lut[i] = [round(a + (b - a) * f) for a, b in zip(c0, c1)]
                break
    return lut


def _bilerp_wrap(g, u, v):
    """Bilinear sample of grid g at fractional (u, v), wrapping (tileable)."""
    cy, cx = g.shape
    u0 = np.floor(u).astype(np.int32)
    v0 = np.floor(v).astype(np.int32)
    fu = (u - u0).astype(np.float32)
    fv = (v - v0).astype(np.float32)
    u0 %= cx
    v0 %= cy
    u1 = (u0 + 1) % cx
    v1 = (v0 + 1) % cy
    top = g[v0, u0] * (1 - fu) + g[v0, u1] * fu
    bot = g[v1, u0] * (1 - fu) + g[v1, u1] * fu
    return top * (1 - fv) + bot * fv


class _Octave:
    """One scrolling layer of tileable value noise."""

    def __init__(self, rng, gw, gh, cells_x, speed_cells_s, drift_deg):
        cells_y = max(2, round(cells_x * gh / gw))
        self.grid = rng.random((cells_y, cells_x)).astype(np.float32)
        a = math.radians(drift_deg)
        self.vel = (math.cos(a) * speed_cells_s, math.sin(a) * speed_cells_s)
        self.off = [rng.random() * cells_x, rng.random() * cells_y]
        ys, xs = np.mgrid[0:gh, 0:gw].astype(np.float32)
        self._u = xs * (cells_x / gw)
        self._v = ys * (cells_y / gh)

    def advance(self, dt):
        self.off[0] += self.vel[0] * dt
        self.off[1] += self.vel[1] * dt

    def sample(self):
        return _bilerp_wrap(self.grid, self._u + self.off[0], self._v + self.off[1])


def _poly_mask(pts, w, h):
    """Even-odd scanline fill of a polygon given in pixel coords (may exceed
    the canvas — clamped), plus a 1-px feather so the mask edge doesn't alias."""
    m = np.zeros((h, w), np.float32)
    n = len(pts)
    for y in range(h):
        yc = y + 0.5
        xs = []
        for i in range(n):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % n]
            if (y1 <= yc < y2) or (y2 <= yc < y1):
                xs.append(x1 + (yc - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for a, b in zip(xs[::2], xs[1::2]):
            lo = max(0, int(math.ceil(a - 0.5)))
            hi = min(w, int(math.floor(b - 0.5)) + 1)
            if hi > lo:
                m[y, lo:hi] = 1.0
    soft = m.copy()
    soft[1:, :] += m[:-1, :]
    soft[:-1, :] += m[1:, :]
    soft[:, 1:] += m[:, :-1]
    soft[:, :-1] += m[:, 1:]
    return np.clip(soft / 5.0 * 1.3, 0.0, 1.0)


def _static_noise(rng, h, w, cells_x):
    """One frozen layer of tileable value noise, sampled at (h, w)."""
    cells_y = max(2, round(cells_x * h / w))
    g = rng.random((cells_y, cells_x)).astype(np.float32)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    return _bilerp_wrap(g, xs * (cells_x / w), ys * (cells_y / h))


def _scale_patch(col, alpha, carve, scale):
    """Nearest-neighbor rescale of a precomputed stone patch (transitions)."""
    h, w = alpha.shape[:2]
    nh, nw = max(3, int(h * scale)), max(3, int(w * scale))
    yi = np.clip((np.arange(nh) / scale).astype(np.int32), 0, h - 1)
    xi = np.clip((np.arange(nw) / scale).astype(np.int32), 0, w - 1)
    return col[yi][:, xi], alpha[yi][:, xi], carve[yi][:, xi]


class _Stone:
    __slots__ = ('sid', 'wx', 'wz', 'px', 'py', 'state', 't0', 'cooldown_until',
                 'bob', 'glint')

    def __init__(self, sid, wx, wz, px, py, bob):
        self.sid = sid
        self.wx, self.wz = wx, wz
        self.px, self.py = px, py
        self.state = 'up'            # up | sinking | down | rising
        self.t0 = -1e9
        self.cooldown_until = 0.0
        self.bob = bob
        self.glint = 0.0

    def phase(self, t):
        """0..1 progress through sinking/rising; 1 when settled."""
        if self.state == 'sinking':
            return min(1.0, (t - self.t0) / SINK_S)
        if self.state == 'rising':
            return min(1.0, (t - self.t0) / RISE_S)
        return 1.0


class _Track:
    __slots__ = ('x', 'z', 'vx', 'vz', 'last', 'stone', 'since')

    def __init__(self, x, z, t):
        self.x, self.z = x, z
        self.vx = self.vz = 0.0
        self.last = t
        self.stone = None
        self.since = 0.0


class LavaShow:
    def __init__(self, layout, grid_w=256, seed=20260722):
        P = layout['projection']
        H = layout['hex_center']
        img = P['image']
        self.timeout_s = P.get('timeout_s', 60)
        self.gw = grid_w
        self.gh = int(round(grid_w * img['d'] / img['w']))
        self.ppm = self.gw / img['w']
        yaw = math.radians(P['projector'].get('yaw_deg', 0))
        self._fwd = (math.sin(yaw), math.cos(yaw))
        self._lat = (math.cos(yaw), -math.sin(yaw))
        self._c = tuple(img['center'])
        self._iw, self._id = img['w'], img['d']

        # deck outline: hexagon + the door slivers out to the shared wing
        # frames (port of buildProjection's deckPts)
        V = [(H['cx'] + H['side'] * math.cos(math.pi / 6 + k * math.pi / 3),
              H['cz'] + H['side'] * math.sin(math.pi / 6 + k * math.pi / 3))
             for k in range(6)]
        room = (layout.get('rooms') or {}).get(P.get('room'), {})
        if 'x' in room:
            wW, wE = room['x'], room['x'] + room['w']
        else:
            wW, wE = V[2][0], V[0][0]
        deck = [V[1], V[2], (wW, V[2][1]), (wW, V[3][1]), V[3], V[4], V[5],
                (wE, V[5][1]), (wE, V[0][1]), V[0]]
        self.mask = _poly_mask([self.to_px(x, z) for x, z in deck], self.gw, self.gh)
        interior = np.argwhere(self.mask > 0.95)
        self._mask_pts = interior if len(interior) else np.argwhere(self.mask > 0)

        pole = (H.get('center_pole') or {})
        mx, my = self.to_px(H['cx'], H['cz'])
        self.mast = (mx, my, (pole.get('od', 0.09) / 2 + 0.05) * self.ppm)
        self._cx, self._cz = H['cx'], H['cz']
        self._wW, self._wE = wW, wE

        self._rng = random.Random(seed)
        nrng = np.random.default_rng(seed)
        self._octaves = [
            _Octave(nrng, self.gw, self.gh, 7, 0.055, 15),
            _Octave(nrng, self.gw, self.gh, 17, 0.16, 205),
            _Octave(nrng, self.gw, self.gh, 41, 0.55, 100),
        ]
        self._oct_w = (0.55, 0.30, 0.15)

        self.t = 0.0
        self.fade = 0.0
        self.active = False
        self._last_presence = -1e9
        self._last_sink = -1e9
        self.tracks = {}
        self.bubbles = []
        self.events = []
        self.event_total = 0  # absolute count; events holds the tail (capped)
        self._heat = np.zeros((self.gh, self.gw), np.float32)
        self._heat_t = -1.0
        self._interior = {}
        self.embers = []
        self.stones = self._place_stones()

        # rock textures: numeral = chain order 1..N (Mayan dots-and-bars,
        # wayfinding across the crossing); the spare carries the shell-zero.
        # Glyphs orient along the direction of travel. Precomputed once —
        # per-frame stone work is a plain alpha blend.
        up = [s for s in self.stones if s.state == 'up']
        self._patches = {}
        for i, s in enumerate(up):
            ref = up[i + 1] if i + 1 < len(up) else up[i - 1]
            heading = math.atan2(ref.py - s.py, ref.px - s.px)
            self._patches[s.sid] = self._build_rock_patch(
                STONE_R_M * self.ppm, seed + 11 * s.sid, numeral=i + 1, heading=heading)
        for s in self.stones:
            if s.sid not in self._patches:
                self._patches[s.sid] = self._build_rock_patch(
                    STONE_R_M * self.ppm, seed + 11 * s.sid, numeral=0, heading=0.0)
        self._island = self._build_island_patch(seed)

        # canopy dapple: soft leaf-shadow blotches hugging the deck rim — the
        # jungle pressing in at the chamber edge. Static, one multiply/frame.
        m = (self.mask > 0.9).astype(np.uint8)
        depth = np.zeros(self.mask.shape, np.float32)
        cur = m.copy()
        K = max(1, int(0.5 * self.ppm))
        for _ in range(K):
            e = cur.copy()
            e[1:, :] &= cur[:-1, :]
            e[:-1, :] &= cur[1:, :]
            e[:, 1:] &= cur[:, :-1]
            e[:, :-1] &= cur[:, 1:]
            e[0, :] = 0
            e[-1, :] = 0
            e[:, 0] = 0
            e[:, -1] = 0
            depth += e
            cur = e
        edge_w = 1.0 - np.clip(depth / K, 0.0, 1.0)
        blob = _static_noise(np.random.default_rng(seed + 5), self.gh, self.gw, 6)
        blob = np.clip((blob - 0.45) * 2.2, 0.0, 1.0)
        self._dapple = (1.0 - DAPPLE_STRENGTH * edge_w * blob)[..., None].astype(np.float32)

    # ---- geometry ----
    def to_px(self, wx, wz):
        dx, dz = wx - self._c[0], wz - self._c[1]
        return ((dx * self._lat[0] + dz * self._lat[1] + self._iw / 2) * self.ppm,
                (dx * self._fwd[0] + dz * self._fwd[1] + self._id / 2) * self.ppm)

    def _interior_pts(self, margin_m):
        """Candidate points at least margin_m (diamond metric) inside the lit
        deck AND off the image border — stones clipped by the projection edge
        read as broken, so the canvas border erodes like a deck edge."""
        key = int(round(margin_m * self.ppm))
        if key not in self._interior:
            m = (self.mask > 0.9).astype(np.uint8)
            for _ in range(key):
                e = m.copy()
                e[1:, :] &= m[:-1, :]
                e[:-1, :] &= m[1:, :]
                e[:, 1:] &= m[:, :-1]
                e[:, :-1] &= m[:, 1:]
                e[0, :] = 0
                e[-1, :] = 0
                e[:, 0] = 0
                e[:, -1] = 0
                m = e
            self._interior[key] = np.argwhere(m > 0)
        return self._interior[key]

    def _snap_interior(self, px, py, pts_set, max_r=24):
        """Nearest interior grid point to (px, py), spiral search."""
        x0, y0 = int(round(px)), int(round(py))
        if (y0, x0) in pts_set:
            return float(x0), float(y0)
        for r in range(1, max_r):
            for dy in range(-r, r + 1):
                for dx in (-r, r) if abs(dy) != r else range(-r, r + 1):
                    if (y0 + dy, x0 + dx) in pts_set:
                        return float(x0 + dx), float(y0 + dy)
        return None

    def _place_stones(self):
        """A walkable stepping chain across the deck — Cuddle CROSS is a
        crossing, so the stones run door sliver to door sliver (east to west)
        at stride spacing, bending around the mast island (which sits dead on
        the straight line). Plus one off-chain spare that starts sunk, so the
        very first mischief sink already has a stone to raise in trade."""
        pts = self._interior_pts(STONE_R_M + STONE_EDGE_MARGIN_M)
        pts_set = {(int(y), int(x)) for y, x in pts}
        r_px = STONE_R_M * self.ppm

        side = self._rng.choice((-1.0, 1.0))
        bend_z = self._cz + side * 0.55
        way = [(self._wE - 0.32, self._cz), (self._cx + 0.45, bend_z),
               (self._cx - 0.45, bend_z), (self._wW + 0.32, self._cz)]

        # resample the polyline at stride spacing, in world meters
        chain, carry = [], 0.0
        for (ax, az), (bx, bz) in zip(way, way[1:]):
            seg = math.hypot(bx - ax, bz - az)
            t = carry
            while t <= seg:
                f = t / seg
                chain.append((ax + (bx - ax) * f, az + (bz - az) * f))
                t += CHAIN_SPACING_M
            carry = t - seg
        if math.hypot(chain[-1][0] - way[-1][0], chain[-1][1] - way[-1][1]) > 0.3:
            chain.append(way[-1])

        stones = []
        for wx, wz in chain[:STONE_N]:
            wx += self._rng.uniform(-CHAIN_JITTER_M, CHAIN_JITTER_M)
            wz += self._rng.uniform(-CHAIN_JITTER_M, CHAIN_JITTER_M)
            snapped = self._snap_interior(*self.to_px(wx, wz), pts_set)
            if snapped is None:
                continue
            px, py = snapped
            if math.hypot(px - self.mast[0], py - self.mast[1]) < self.mast[2] + r_px + 0.25 * self.ppm:
                continue
            if any(math.hypot(px - s.px, py - s.py) < 0.45 * self.ppm for s in stones):
                continue
            wx, wz = self._px_to_world(px, py)
            stones.append(_Stone(len(stones), wx, wz, px, py, self._rng.random() * math.tau))

        # off-chain spare, farthest-from-chain dart, starting sunk
        best, best_d = None, -1.0
        for _ in range(80):
            py, px = pts[self._rng.randrange(len(pts))]
            px, py = float(px), float(py)
            if math.hypot(px - self.mast[0], py - self.mast[1]) < self.mast[2] + r_px + 0.25 * self.ppm:
                continue
            d = min((math.hypot(px - s.px, py - s.py) for s in stones), default=1e9)
            if 0.45 * self.ppm < d and d > best_d:
                best, best_d = (px, py), d
        if best:
            wx, wz = self._px_to_world(*best)
            spare = _Stone(len(stones), wx, wz, best[0], best[1], self._rng.random() * math.tau)
            spare.state = 'down'
            stones.append(spare)
        return stones

    def _px_to_world(self, px, py):
        lx = px / self.ppm - self._iw / 2
        ly = py / self.ppm - self._id / 2
        return (self._c[0] + lx * self._lat[0] + ly * self._fwd[0],
                self._c[1] + lx * self._lat[1] + ly * self._fwd[1])

    # ---- inputs ----
    def set_tracks(self, tracks):
        """tracks: iterable of {'id', 'x', 'z'} in world meters (already at
        sensor cadence/latency — the engine adds none of its own)."""
        for tr in tracks:
            tid = tr['id']
            t = self.tracks.get(tid)
            if t is None:
                self.tracks[tid] = _Track(tr['x'], tr['z'], self.t)
                continue
            dt = max(1e-3, self.t - t.last)
            vx, vz = (tr['x'] - t.x) / dt, (tr['z'] - t.z) / dt
            t.vx += (vx - t.vx) * TRACK_VEL_EMA
            t.vz += (vz - t.vz) * TRACK_VEL_EMA
            t.x, t.z, t.last = tr['x'], tr['z'], self.t
        if tracks:
            self.cue('presence')

    def _emit(self, ev):
        self.events.append(ev)
        self.event_total += 1
        if len(self.events) > 400:
            del self.events[:200]

    def fresh_events(self, seen_total):
        """Events appended after seen_total; pair with the new event_total.
        Lets several stream clients read the log without draining each other."""
        missed = min(self.event_total - seen_total, len(self.events))
        return (self.events[-missed:] if missed > 0 else []), self.event_total

    def cue(self, source='cue'):
        self._last_presence = self.t
        if not self.active:
            self.active = True
            self._emit({'e': 'show_on', 'src': source})

    # ---- simulation ----
    def step(self, dt):
        self.t += dt
        for tid in [k for k, v in self.tracks.items() if self.t - v.last > TRACK_STALE_S]:
            del self.tracks[tid]
        if self.active and self.t - self._last_presence > self.timeout_s:
            self.active = False
            self._emit({'e': 'show_off'})
        self.fade = min(1.0, max(0.0, self.fade + (dt if self.active else -dt) * FADE_PER_S))
        for o in self._octaves:
            o.advance(dt)
        self._step_stones()
        self._step_mischief()
        self._step_bubbles(dt)
        self._step_embers(dt)
        self._step_glints(dt)

    def _step_stones(self):
        for s in self.stones:
            if s.state == 'sinking' and s.phase(self.t) >= 1.0:
                s.state = 'down'
            elif s.state == 'rising' and s.phase(self.t) >= 1.0:
                s.state = 'up'

    def _step_mischief(self):
        if self.fade <= 0:
            return
        up = [s for s in self.stones if s.state == 'up']
        for t in self.tracks.values():
            speed = math.hypot(t.vx, t.vz)
            if speed < WALK_SPEED_GATE:
                t.stone, t.since = None, 0.0
                continue
            ux, uz = t.vx / speed, t.vz / speed
            best, best_dot = None, APPROACH_DOT
            for s in up:
                dx, dz = s.wx - t.x, s.wz - t.z
                d = math.hypot(dx, dz)
                if not (APPROACH_NEAR_M <= d <= APPROACH_FAR_M):
                    continue
                dot = (dx * ux + dz * uz) / d
                if dot > best_dot:
                    best, best_dot = s, dot
            if best is None or best is not t.stone:
                t.stone, t.since = best, self.t
                continue
            if (self.t - t.since >= DWELL_S
                    and self.t >= best.cooldown_until
                    and self.t - self._last_sink >= GLOBAL_COOLDOWN_S
                    and len(up) > STONE_MIN_UP):
                self._sink(best, t)
                t.stone = None

    def _sink(self, stone, track):
        stone.state = 'sinking'
        stone.t0 = self.t
        stone.cooldown_until = self.t + STONE_COOLDOWN_S + SINK_S
        self._last_sink = self.t
        self._emit({'e': 'sink', 'id': stone.sid, 'x': stone.px, 'y': stone.py})
        self._burst(stone.px, stone.py, 6)
        down = [s for s in self.stones if s.state == 'down' and s is not stone]
        if down:
            riser = self._rng.choice(down)
            spot = self._rise_spot(track)
            if spot:
                riser.wx, riser.wz = spot
                riser.px, riser.py = self.to_px(*spot)
            riser.state = 'rising'
            riser.t0 = self.t + 0.5  # beat of suspense before the replacement surfaces
            riser.cooldown_until = self.t + STONE_COOLDOWN_S + RISE_S
            self._emit({'e': 'rise', 'id': riser.sid, 'x': riser.px, 'y': riser.py})
            self._burst(riser.px, riser.py, 4)

    def _rise_spot(self, track):
        """Pick a spot 0.9–2.0 m from the walker, biased to the side of their
        heading (redirect, don't reward the straight line)."""
        speed = math.hypot(track.vx, track.vz)
        hx, hz = (track.vx / speed, track.vz / speed) if speed > 1e-6 else (0.0, 1.0)
        pts = self._interior_pts(STONE_R_M + STONE_EDGE_MARGIN_M)
        best, best_score = None, -1e9
        for _ in range(60):
            py, px = pts[self._rng.randrange(len(pts))]
            px, py = float(px), float(py)
            if math.hypot(px - self.mast[0], py - self.mast[1]) < self.mast[2] + (STONE_R_M + 0.30) * self.ppm:
                continue
            wx, wz = self._px_to_world(px, py)
            if any(s.state != 'down' and math.hypot(wx - s.wx, wz - s.wz) < STONE_MIN_SPACE_M
                   for s in self.stones):
                continue
            dx, dz = wx - track.x, wz - track.z
            d = math.hypot(dx, dz)
            if not (0.9 <= d <= 2.0):
                continue
            if any(math.hypot(wx - o.x, wz - o.z) < 0.6 for o in self.tracks.values()):
                continue
            side = abs(dx * hz - dz * hx) / d      # lateral-ness vs heading
            ahead = (dx * hx + dz * hz) / d
            score = side - 0.3 * abs(ahead)
            if score > best_score:
                best, best_score = (wx, wz), score
        return best

    def _burst(self, px, py, n):
        for _ in range(n):
            a = self._rng.random() * math.tau
            r = (0.6 + self._rng.random() * 0.8) * STONE_R_M * self.ppm
            self._spawn_bubble(px + math.cos(a) * r, py + math.sin(a) * r)

    def _spawn_bubble(self, px, py):
        life = BUBBLE_LIFE_S[0] + self._rng.random() * (BUBBLE_LIFE_S[1] - BUBBLE_LIFE_S[0])
        self.bubbles.append({'x': px, 'y': py, 't0': self.t, 'life': life,
                             'r': (0.05 + self._rng.random() * 0.06) * self.ppm})

    def _step_bubbles(self, dt):
        if self.fade > 0 and self._rng.random() < BUBBLE_RATE_HZ * dt * self.fade:
            py, px = self._mask_pts[self._rng.randrange(len(self._mask_pts))]
            self._spawn_bubble(float(px), float(py))
        alive = []
        for b in self.bubbles:
            if self.t - b['t0'] >= b['life']:
                self._emit({'e': 'pop', 'x': round(b['x'], 1), 'y': round(b['y'], 1)})
            else:
                alive.append(b)
        self.bubbles = alive

    def _step_embers(self, dt):
        # sparks drifting off the lava — spawned on the lit deck, slow wander
        if (self.fade > 0 and len(self.embers) < EMBER_MAX
                and self._rng.random() < EMBER_RATE_HZ * dt * self.fade):
            py, px = self._mask_pts[self._rng.randrange(len(self._mask_pts))]
            a = self._rng.random() * math.tau
            sp = self._rng.uniform(0.05, 0.12) * self.ppm
            self.embers.append({
                'x': float(px), 'y': float(py),
                'vx': math.cos(a) * sp, 'vy': math.sin(a) * sp,
                't0': self.t,
                'life': self._rng.uniform(*EMBER_LIFE_S)})
        alive = []
        for e in self.embers:
            if self.t - e['t0'] < e['life']:
                e['x'] += e['vx'] * dt
                e['y'] += e['vy'] * dt
                alive.append(e)
        self.embers = alive

    def _step_glints(self, dt):
        # the glyph notices an approaching walker (idle stones only)
        k = min(1.0, dt * 6.0)
        fresh = [t for t in self.tracks.values() if self.t - t.last < TRACK_STALE_S]
        for s in self.stones:
            if s.state != 'up' or not fresh:
                s.glint += (0.0 - s.glint) * k
                continue
            dmin = min(math.hypot(t.x - s.wx, t.z - s.wz) for t in fresh)
            target = np.clip(1.0 - (dmin - 0.35) / GLINT_R_M, 0.0, 1.0) * 0.55
            s.glint += (float(target) - s.glint) * k

    # ---- output ----
    def _heat_field(self):
        # memoized on engine time: render() and the sim's heat stream may both
        # ask within one tick, and blob adds must not double up
        if self._heat_t == self.t:
            return self._heat
        self._heat_t = self.t
        h = sum(w * o.sample() for w, o in zip(self._oct_w, self._octaves))
        h = h ** 1.5
        for b in self.bubbles:
            a = (self.t - b['t0']) / b['life']
            self._add_blob(h, b['x'], b['y'], b['r'] * (0.6 + 2.2 * a), 0.55 * a)
        for t in self.tracks.values():
            if self.t - t.last < TRACK_STALE_S:
                px, py = self.to_px(t.x, t.z)
                self._add_blob(h, px, py, RECOIL_R_M * self.ppm, RECOIL_AMOUNT)
        for s in self.stones:
            if s.state == 'sinking':
                self._add_blob(h, s.px, s.py, STONE_R_M * self.ppm * 1.3, 0.8 * s.phase(self.t))
        for e in self.embers:
            env = math.sin(math.pi * (self.t - e['t0']) / e['life'])
            self._add_blob(h, e['x'], e['y'], 1.8, 0.55 * env)
        np.clip(h, 0.0, 1.0, out=h)
        self._heat = h
        return h

    def _add_blob(self, h, px, py, r, amount, ring=False):
        x0, x1 = max(0, int(px - 2 * r)), min(self.gw, int(px + 2 * r) + 1)
        y0, y1 = max(0, int(py - 2 * r)), min(self.gh, int(py + 2 * r) + 1)
        if x1 <= x0 or y1 <= y0:
            return
        ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        d = np.hypot(xs - px, ys - py)
        if ring:
            g = np.exp(-((d - r) / (r * 0.35)) ** 2)
        else:
            g = np.exp(-(d / r) ** 2)
        h[y0:y1, x0:x1] += amount * g

    def render(self, lut=None):
        """uint8 (gh, gw, 3) frame: heat through the palette, stones on top,
        deck mask + fade applied. Off-deck pixels stay black — the mask IS the
        projection mapping."""
        if self.fade <= 0:
            return np.zeros((self.gh, self.gw, 3), np.uint8)
        lut = lut if lut is not None else _LUT
        heat = self._heat_field()
        rgb = lut[(heat * 255).astype(np.uint8)].astype(np.float32)
        for s in self.stones:
            self._draw_stone(rgb, s)
        self._draw_island(rgb)
        np.clip(rgb, 0.0, 255.0, out=rgb)  # never let float sums wrap in uint8
        rgb *= self._dapple  # canopy shadow falls on lava and stones alike
        rgb *= (self.mask * self.fade)[..., None]
        return rgb.astype(np.uint8)

    def _build_rock_patch(self, r, seed, numeral=None, heading=0.0,
                          edge_col=_STONE_EDGE, core_col=_STONE_CORE):
        """A weathered rock as (color, alpha, carve) arrays: wobbled outline
        (no perfect circles in a temple), mottle + speckle + thin crack
        veins, soft top-left key light, and an optional chiseled Mayan
        numeral (dots and bars; 0 = the shell glyph). Replace-composited —
        no additive terms (uint8 wrap lesson, 2026-07-22)."""
        rng = np.random.default_rng(seed)
        pad = int(math.ceil(r * 1.18)) + 3
        s = 2 * pad + 1
        ys, xs = np.mgrid[0:s, 0:s].astype(np.float32)
        dx, dy = xs - pad, ys - pad
        d = np.hypot(dx, dy)
        th = np.arctan2(dy, dx)
        wob_tab = rng.random(16).astype(np.float32) * 2 - 1
        idx = (th + math.pi) / math.tau * 16
        i0 = np.floor(idx).astype(np.int32) % 16
        f = (idx - np.floor(idx)).astype(np.float32)
        wob = wob_tab[i0] * (1 - f) + wob_tab[(i0 + 1) % 16] * f
        edge_r = np.maximum(r * (1 + 0.09 * wob), 1e-3)
        alpha = np.clip((edge_r - d) / 1.5, 0.0, 1.0)[..., None]
        shade = np.clip(1.0 - d / edge_r, 0.0, 1.0)[..., None] ** 0.6
        lam = 0.86 + 0.14 * np.clip((-dx * 0.45 - dy * 0.89) / edge_r, -1, 1)
        mottle = 0.82 + 0.36 * _static_noise(rng, s, s, max(3, s // 7))
        speck = 0.96 + 0.08 * _static_noise(rng, s, s, max(4, s // 3))
        veins = _static_noise(rng, s, s, max(3, s // 5))
        crack_line = np.clip(1.0 - np.abs(veins - 0.5) / 0.035, 0.0, 1.0)
        tint = np.float32(rng.uniform(-7, 7))  # per-stone value shift, grey-preserving
        carve = np.zeros((s, s), np.float32)
        if numeral is not None:
            carve = self._numeral_carve(dx, dy, r, numeral, heading)
        # the mason dressed the surface before carving: cracks and speckle
        # fade out inside the glyph zone so the numeral stays legible
        crack = 1.0 - 0.35 * crack_line * (1.0 - carve)
        col = edge_col + (core_col - edge_col) * shade + tint
        col = col * (lam * mottle * speck * crack)[..., None]
        if numeral is not None:
            col = col * (1.0 - carve[..., None] * (1.0 - _CARVE_DARK))
            lip = np.clip(np.roll(carve, 2, axis=0) - carve, 0.0, 1.0)
            col = col + lip[..., None] * 22.0  # chisel lip catches the light
        return col.astype(np.float32), alpha.astype(np.float32), carve.astype(np.float32)

    @staticmethod
    def _numeral_carve(dx, dy, r, n, heading):
        """Mayan numeral as a carve mask: n%5 dots above n//5 stacked bars,
        oriented along the walking direction; n=0 is the shell glyph."""
        ca, sa = math.cos(heading), math.sin(heading)
        u = dx * ca + dy * sa
        v = -dx * sa + dy * ca
        m = np.zeros(dx.shape, np.float32)

        def groove(dist):
            return np.clip(-dist / 1.7, 0.0, 1.0)

        if n == 0:
            de = np.hypot(u / 1.45, v)
            m = np.maximum(m, groove(np.abs(de - 0.34 * r) - 0.07 * r))
            m = np.maximum(m, groove(np.maximum(np.abs(u) - 0.16 * r,
                                                np.abs(v) - 0.06 * r)))
            return m
        bars, dots = divmod(n, 5)
        for b in range(bars):
            bv = (0.16 + 0.32 * b) * r
            m = np.maximum(m, groove(np.maximum(np.abs(u) - 0.42 * r,
                                                np.abs(v - bv) - 0.10 * r)))
        if dots:
            span = 0.32 * r * (dots - 1)
            for k in range(dots):
                du = -span / 2 + 0.32 * r * k
                m = np.maximum(m, groove(np.hypot(u - du, v + 0.22 * r) - 0.145 * r))
        return m

    def _build_island_patch(self, seed):
        """The mast base as a carved sun-stone altar: rock texture, two
        concentric carved rings, twelve tick marks, a center pit."""
        R = self.mast[2] + 0.06 * self.ppm
        col, alpha, _ = self._build_rock_patch(R, seed + 97, numeral=None,
                                               edge_col=_ISLAND_EDGE,
                                               core_col=_ISLAND_CORE)
        s = col.shape[0]
        pad = s // 2
        ys, xs = np.mgrid[0:s, 0:s].astype(np.float32)
        dx, dy = xs - pad, ys - pad
        d = np.hypot(dx, dy)
        th = np.arctan2(dy, dx)
        carve = np.zeros((s, s), np.float32)
        for rr in (0.46, 0.78):
            carve = np.maximum(carve, np.clip(1.0 - np.abs(d - rr * R) / 1.2, 0.0, 1.0))
        tick = ((np.abs(((th / math.tau * 12) % 1.0) - 0.5) < 0.10)
                & (d > 0.50 * R) & (d < 0.74 * R))
        carve = np.maximum(carve, tick.astype(np.float32))
        carve = np.maximum(carve, np.clip(1.0 - d / (0.10 * R), 0.0, 1.0))
        col *= (1.0 - carve[..., None] * (1.0 - _CARVE_DARK))
        return col, alpha

    def _composite_patch(self, rgb, cx, cy, col, alpha, show=None):
        h, w = alpha.shape[:2]
        x0 = int(round(cx)) - w // 2
        y0 = int(round(cy)) - h // 2
        sx0, sy0 = max(0, -x0), max(0, -y0)
        x0, y0 = max(0, x0), max(0, y0)
        x1 = min(self.gw, x0 + w - sx0)
        y1 = min(self.gh, y0 + h - sy0)
        if x1 <= x0 or y1 <= y0:
            return
        a = alpha[sy0:sy0 + y1 - y0, sx0:sx0 + x1 - x0]
        c = (show if show is not None else col)[sy0:sy0 + y1 - y0, sx0:sx0 + x1 - x0]
        region = rgb[y0:y1, x0:x1]
        region[:] = region * (1 - a) + c * a

    def _draw_stone(self, rgb, s):
        if s.state == 'down':
            return
        ph = s.phase(self.t)
        col, alpha, carve = self._patches[s.sid]
        if s.state == 'sinking':
            scale, heatmix = 1.0 - 0.55 * ph, ph
        elif s.state == 'rising':
            if self.t < s.t0:
                return
            scale, heatmix = 0.45 + 0.55 * ph, (1.0 - ph) * 0.8
        else:
            scale, heatmix = 1.0, 0.0
        if scale != 1.0:
            col, alpha, carve = _scale_patch(col, alpha, carve, scale)
        show = col
        if heatmix > 0:
            # the glyph heats first — a beat of warning before the melt
            mixmap = np.maximum(carve * min(1.0, heatmix * 2.5), heatmix)[..., None]
            show = col * (1 - mixmap) + _STONE_HOT * mixmap
        elif s.glint > 0.02:
            g = (carve * s.glint)[..., None]
            show = col + g * (_AMBER - col) * 0.8
        self._composite_patch(rgb, s.px, s.py, col, alpha, show)

    def _draw_island(self, rgb):
        col, alpha = self._island
        self._composite_patch(rgb, self.mast[0], self.mast[1], col, alpha)

    def hello_patches(self):
        """The precomputed rock artwork for the sim page (one-time, hello
        message): every stone plus the altar as raw RGBA — the browser draws
        the SAME pixels production projects, no second texture implementation."""
        def pack(col, alpha):
            rgba = np.concatenate(
                [np.clip(col, 0, 255), alpha * 255], axis=2).astype(np.uint8)
            return {'w': rgba.shape[1], 'h': rgba.shape[0],
                    'rgba': base64.b64encode(rgba.tobytes()).decode()}

        stones = []
        for s in self.stones:
            col, alpha, _ = self._patches[s.sid]
            stones.append({'id': s.sid, **pack(col, alpha)})
        icol, ialpha = self._island
        island = {'x': round(self.mast[0], 1), 'y': round(self.mast[1], 1),
                  **pack(icol, ialpha)}
        return {'stones': stones, 'island': island}

    def heat_b64(self, step=2):
        """Downsampled heat field for the sim stream (uint8, base64)."""
        if self.fade > 0:
            self._heat_field()
        return base64.b64encode(
            (self._heat[::step, ::step] * 255).astype(np.uint8).tobytes()).decode()

    def state(self, drain_events=True):
        st = {
            'fade': round(self.fade, 3),
            'active': self.active,
            'grid': [self.gw, self.gh],
            'stones': [{'id': s.sid, 'x': round(s.px, 1), 'y': round(s.py, 1),
                        'r': round(STONE_R_M * self.ppm, 1), 'state': s.state,
                        'phase': round(s.phase(self.t), 3),
                        'glint': round(s.glint, 2)} for s in self.stones],
            'tracks': [dict(zip(('x', 'y'),
                                map(lambda v: round(v, 1), self.to_px(t.x, t.z))))
                       for t in self.tracks.values()],
            'events': self.events if drain_events else list(self.events),
        }
        if drain_events:
            self.events = []
        return st


_LUT = palette_lut()
