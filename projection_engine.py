"""Cuddle Cross floor projection — the floor-show engines.

One deck, two selectable shows (THEMES), same skeleton:

  lava    — stepping stones on molten lava (wiring-guides/cuddle-lava-plan.md):
            the deck is a flowing heat field, ~5 chain stones + a spare ride on
            it, tracked walkers get played with (a stone someone is clearly
            walking toward sinks while another rises off to the side), bubbles
            pop, Kukulkan breaches occasionally.
  jungle  — the temple floor reclaimed (wiring-guides/cuddle-jungle-plan.md):
            sun-dappled undergrowth, snakes that slither across the deck and
            dart away from feet, fallen glyph stones going mossy, fireflies,
            and a sun-pool that follows each walker.

One engine, two displays: the sim streams state + the scalar field to the
browser (sim/sim_ui.py /sim/projection), production renders fullscreen to the
LS625X (projection_renderer.py --theme). Pure numpy — no GUI deps. Inputs are
tracked positions in world meters (LD2450 or the sim avatar); callers drive
time via step(dt), so behavior is reproducible in tests.

Geometry (world->image mapping, deck-outline mask, mast island) is a port of
the sim preview's buildProjection (sim/web/app.js) against the same
maze_layout.json `projection` key — the two must agree or the sim lies.
"""
import base64
import math
import random

import numpy as np

# ---- LAVA tuning knobs (see the plan doc; all distances meters, times s) ----
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

# ---- the monster: Kukulkan shows his head occasionally ----
MONSTER_GAP_S = (45.0, 100.0)   # quiet time between appearances
MONSTER_FIRST_S = (16.0, 26.0)  # first appearance after the show cues
MONSTER_SWIM_S = (4.0, 7.0)     # underlava approach
MONSTER_RISE_S = 1.1
MONSTER_HOLD_S = (2.2, 4.2)     # head up, looking around
MONSTER_SINK_S = 0.9
MONSTER_HEAD_L_M = 0.30         # head half-length (snout to skull)
MONSTER_HEAD_W_M = 0.17         # head half-width
MONSTER_ROT_STEPS = 16          # precomputed head orientations (production)
_OBSIDIAN = np.array([44, 52, 46], np.float32)
_JADE = np.array([44, 116, 78], np.float32)
_EYE_AMBER = np.array([255, 200, 90], np.float32)
_EYE_CORE = np.array([255, 242, 195], np.float32)
_EMBER_RIM = np.array([214, 92, 24], np.float32)  # lava underlight on the head's edge

# ---- JUNGLE tuning knobs (wiring-guides/cuddle-jungle-plan.md) ----
SNAKE_SPECS = [
    {'kind': 'rattler', 'len_m': 1.55, 'r_m': 0.062},  # tzabcan diamondback
    {'kind': 'gold', 'len_m': 1.30, 'r_m': 0.054},     # gold eyelash viper
    {'kind': 'coral', 'len_m': 1.05, 'r_m': 0.042},
]
SNAKE_HEAD_X = 2.3           # head length as a multiple of body half-width
SNAKE_DIAMOND_PER_M = 0.17   # diamond-chain period down the rattler's back
RATTLE_M = 0.11              # the rattle: last stretch of the rattler's tail...
RATTLE_RING_M = 0.018        # ...as alternating keratin rings, held wider
                             # than a normal tail tip (see the profile knots)
SNAKE_FIELD_STEP = 2         # snake distance field lattice stride (2 = half-res
                             # body raster, 4x cheaper on the Pi; eyes/tongue
                             # stay full-res, edges soften ~1 px)
SNAKE_CORAL_PER_M = 0.22     # coral ring period (red widest, "red touches yellow")
SNAKE_SEG_M = 0.045          # spine resample spacing (< body radius: solid on curves)
SNAKE_SPEED = (0.16, 0.30)   # cruise m/s (each snake draws its own)
SNAKE_FLEE_SPEED = 0.62
SNAKE_FLEE_R_M = 0.75        # feet closer than this spook the snake...
SNAKE_CALM_X = 1.6           # ...and it stays spooked until this factor further out
SNAKE_FLEE_EV_GAP_S = 4.0    # min quiet time between flee events per snake
SNAKE_TURN = 2.4             # rad/s steering gain toward the goal
SNAKE_WEAVE = (1.3, 2.4)     # rad/s slither S-curve amplitude range
SNAKE_WEAVE_HZ = (0.45, 0.85)
SNAKE_GOAL_S = 22.0          # give up on an unreached goal after this long
TONGUE_GAP_S = (2.5, 7.0)
TONGUE_FLICK_S = 0.35
WAKE_DEP = 0.12              # parted-grass glow deposited per second at the head
WAKE_TAU_S = 2.2             # ...and how fast the wake settles back
SUN_R_M = 0.42               # the canopy opens over each walker
SUN_AMOUNT = 0.30
FIREFLY_N = 7
FIREFLY_LIFE_S = (9.0, 22.0)
GLYPH_N = 3                  # fallen carved stones going mossy
GLYPH_R_M = 0.15

# jungle LIGHT ramp (multiplies the leaf-litter base): deep canopy shadow
# with a green cast -> neutral -> warm gold where the sun breaks through
_JUNGLE_STOPS = [
    (0.00, (74, 88, 62)),
    (0.35, (146, 154, 120)),
    (0.62, (216, 220, 184)),
    (0.85, (250, 242, 198)),
    (1.00, (255, 252, 220)),
]
LEAF_DENSITY = 0.0245        # leaves per grid px^2 (count scales with grid area)

# temple LIGHT ramp: cool stone shadow -> torch-warm gold
_TEMPLE_STOPS = [
    (0.00, (76, 68, 60)),
    (0.35, (148, 132, 110)),
    (0.62, (216, 196, 158)),
    (0.85, (252, 230, 176)),
    (1.00, (255, 244, 204)),
]
MOTE_N = 5                   # drifting dust motes catching the temple light
CARVED_FLAGS = 3             # flagstones carrying a carved glyph (glint on approach)
# scarab swarms, straight out of The Mummy: erupt from a crack mouth,
# skitter across as a mass, circle a walker's feet, drain into another crack
SCARAB_FIRST_S = (10.0, 16.0)
SCARAB_GAP_S = (18.0, 45.0)
SCARAB_N = (24, 36)
HOLE_R_M = (0.055, 0.085)    # the visible pits the swarms use, baked in the floor
SCARAB_ERUPT_S = 1.2         # how long the crack pours
SCARAB_ORBIT_S = (3.5, 6.0)  # how long they circle the feet
SCARAB_ORBIT_R_M = 0.55
SCARAB_MAX_S = 25.0          # hard cap on a swarm's life (safety vanish)
SCARAB_SPEED = (0.45, 0.85)  # dash speed range m/s (they move in bursts)
SCARAB_L_M = 0.07            # body length
SCARAB_ROT_STEPS = 16
_SCARAB_BODY = np.array([22, 17, 11], np.float32)
_SCARAB_SHEEN = np.array([96, 128, 72], np.float32)  # bronze-green iridescence
# the fallen torch, Indiana Jones style: a BONE wrapped in cloth, dropped
# at the deck edge and still burning — bone + wrap + scorch baked into the
# floor (pale bone reads on dark stone), live flame + guttering light pool
TORCH_BONE_M = 0.44          # femur length, condyle knobs to the wrap
TORCH_WRAP_M = 0.15          # cloth-wrapped end that carries the fire
TORCH_FLAME_M = 0.20         # nominal flame length along the floor
TORCH_POOL_R_M = 0.55        # warm pool the flame throws
TORCH_SPUTTER_S = (20.0, 50.0)  # gap between gutters (dip, then flare)
_BONE = np.array([214, 204, 178], np.float32)
_BONE_DARK = np.array([150, 138, 112], np.float32)
_CLOTH = np.array([196, 178, 142], np.float32)
_CLOTH_CHAR = np.array([52, 38, 28], np.float32)
_FLAME_CORE = np.array([255, 244, 200], np.float32)
_FLAME_MID = np.array([255, 190, 70], np.float32)
_FLAME_OUT = np.array([230, 110, 25], np.float32)
_RTL_BASE = np.array([172, 142, 92], np.float32)  # tzabcan sandy tan
_RTL_DARK = np.array([96, 66, 36], np.float32)    # ...diamondback brown
_RTL_RING_A = np.array([202, 182, 144], np.float32)  # rattle keratin buff
_RTL_RING_B = np.array([140, 118, 86], np.float32)
_GOLD_BASE = np.array([218, 172, 54], np.float32)  # eyelash viper gold
_EYE_DARK = np.array([24, 18, 12], np.float32)     # dark eye for the gold body
_CORAL_R = np.array([172, 34, 26], np.float32)    # coral snake rings
_CORAL_Y = np.array([214, 172, 58], np.float32)
_CORAL_K = np.array([24, 22, 20], np.float32)
_SNAKE_EYE = np.array([250, 214, 90], np.float32)
_TONGUE = np.array([205, 62, 48], np.float32)
_MOSS_EDGE = np.array([36, 54, 32], np.float32)   # mossy ruin stone
_MOSS_CORE = np.array([86, 104, 74], np.float32)
_MOSS_GLINT = np.array([205, 235, 130], np.float32)
_FLY_CORE = np.array([255, 240, 170], np.float32)


def palette_lut(stops=None):
    stops = stops if stops is not None else _PALETTE_STOPS
    lut = np.zeros((256, 3), np.uint8)
    for i in range(256):
        t = i / 255.0
        for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
            if p0 <= t <= p1:
                f = (t - p0) / ((p1 - p0) or 1.0)
                lut[i] = [round(a + (b - a) * f) for a, b in zip(c0, c1)]
                break
    return lut


def _angdiff(a, b):
    """Signed smallest angle a-b, in (-pi, pi]."""
    return (a - b + math.pi) % math.tau - math.pi


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
    """One scrolling layer of tileable value noise. The coarse grid is
    expanded to a full-res tileable image ONCE; each frame samples it with
    three np.rolls + a bilinear mix (integer scroll with subpixel blend).
    Re-interpolating the coarse grid per frame cost ~30 ms/octave on the
    Pi 3B+ — the single hottest thing in the show (2026-07-23)."""

    def __init__(self, rng, gw, gh, cells_x, speed_cells_s, drift_deg):
        cells_y = max(2, round(cells_x * gh / gw))
        self.grid = rng.random((cells_y, cells_x)).astype(np.float32)
        a = math.radians(drift_deg)
        self.vel = (math.cos(a) * speed_cells_s, math.sin(a) * speed_cells_s)
        self.off = [rng.random() * cells_x, rng.random() * cells_y]
        ys, xs = np.mgrid[0:gh, 0:gw].astype(np.float32)
        self.img = _bilerp_wrap(self.grid, xs * (cells_x / gw), ys * (cells_y / gh))
        self._sx = gw / cells_x     # px per cell
        self._sy = gh / cells_y

    def advance(self, dt):
        self.off[0] = (self.off[0] + self.vel[0] * dt) % self.grid.shape[1]
        self.off[1] = (self.off[1] + self.vel[1] * dt) % self.grid.shape[0]

    def sample(self):
        ox = self.off[0] * self._sx
        oy = self.off[1] * self._sy
        j0, i0 = int(math.floor(ox)), int(math.floor(oy))
        fx, fy = np.float32(ox - j0), np.float32(oy - i0)
        base = np.roll(self.img, (-i0, -j0), (0, 1))
        top = (1 - fx) * base + fx * np.roll(base, -1, 1)
        return (1 - fy) * top + fy * np.roll(top, -1, 0)


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


def _up2(f, h, w):
    """Bilinear 2x upsample of a half-lattice field, cropped to (h, w).
    Used on smooth fields (distance, arc length) — near-exact for them."""
    fh, fw = f.shape
    out = np.empty((fh * 2, fw * 2), np.float32)
    out[0::2, 0::2] = f
    out[0::2, 1:-1:2] = 0.5 * (f[:, :-1] + f[:, 1:])
    out[0::2, -1] = f[:, -1]
    out[1:-1:2] = 0.5 * (out[0:-2:2] + out[2::2])
    out[-1] = out[-2]
    return out[:h, :w]


def _scale_patch(col, alpha, carve, scale):
    """Nearest-neighbor rescale of a precomputed patch (transitions)."""
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


class _Snake:
    __slots__ = ('sid', 'kind', 'x', 'z', 'heading', 'speed', 'spd', 'goal',
                 'goal_t', 'trail', 'n_seg', 'weave_a', 'weave_hz', 'weave_ph',
                 'flee', 'flee_ev', 'tongue_t', 'tongue_on', 'style')

    def __init__(self, sid, kind, x, z, heading, speed, n_seg, weave):
        self.sid = sid
        self.kind = kind
        self.x, self.z = x, z
        self.heading = heading
        self.speed = speed          # cruise; spd is the smoothed live speed
        self.spd = speed
        self.goal = None
        self.goal_t = -1e9
        self.n_seg = n_seg
        self.trail = [(x - math.cos(heading) * SNAKE_SEG_M * i,
                       z - math.sin(heading) * SNAKE_SEG_M * i)
                      for i in range(n_seg)]
        self.weave_a, self.weave_hz, self.weave_ph = weave
        self.flee = False
        self.flee_ev = -1e9
        self.tongue_t = 0.0
        self.tongue_on = False
        self.style = None           # _snake_style bundle (skin + silhouette)


class FloorShow:
    """Shared skeleton of every floor show: deck geometry + mask, the drifting
    noise field, walker tracks, presence/fade, the event log, and the patch /
    blob toolbox. Subclasses fill the theme hooks:

        _setup(seed)      — build theme content (called once, end of __init__)
        _step_theme(dt)   — advance theme content (called from step)
        _field_blobs(h)   — add theme light/heat into the scalar field
        _draw(rgb)        — composite theme entities over the LUT'd field
        _state_extra()    — theme keys merged into state()
        hello_patches()   — precomputed artwork for the sim page
    """

    THEME = 'floor'
    PALETTE_STOPS = _PALETTE_STOPS
    OCTAVES = ((7, 0.055, 15), (17, 0.16, 205), (41, 0.55, 100))
    OCT_WEIGHTS = (0.55, 0.30, 0.15)
    FIELD_GAMMA = 1.5
    DAPPLE = DAPPLE_STRENGTH

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
        self._octaves = [_Octave(nrng, self.gw, self.gh, c, sp, dr)
                         for c, sp, dr in self.OCTAVES]
        self._oct_w = self.OCT_WEIGHTS

        self.t = 0.0
        self.fade = 0.0
        self.active = False
        self._last_presence = -1e9
        self.tracks = {}
        self.events = []
        self.event_total = 0  # absolute count; events holds the tail (capped)
        self._heat = np.zeros((self.gh, self.gw), np.float32)
        self._heat_t = -1.0
        self._interior = {}
        self._stamps = {}  # gaussian blob sprites, keyed (r, ring)
        self._base = None  # static floor texture; None = field->palette direct

        self._setup(seed)

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
        self._dapple = (1.0 - self.DAPPLE * edge_w * blob)[..., None].astype(np.float32)
        # dapple and deck mask folded into ONE static per-frame multiply
        self._env = (self._dapple * self.mask[..., None]).astype(np.float32)

    # ---- theme hooks (subclasses override) ----
    def _setup(self, seed):
        pass

    def _step_theme(self, dt):
        pass

    def _field_blobs(self, h):
        pass

    def _draw(self, rgb):
        pass

    def _state_extra(self):
        return {}

    def hello_patches(self):
        return {}

    # ---- palette ----
    @classmethod
    def lut(cls):
        lut = cls.__dict__.get('_lut')
        if lut is None:
            lut = palette_lut(cls.PALETTE_STOPS)
            cls._lut = lut
        return lut

    def palette_list(self):
        return self.lut().tolist()

    # ---- geometry ----
    def to_px(self, wx, wz):
        dx, dz = wx - self._c[0], wz - self._c[1]
        return ((dx * self._lat[0] + dz * self._lat[1] + self._iw / 2) * self.ppm,
                (dx * self._fwd[0] + dz * self._fwd[1] + self._id / 2) * self.ppm)

    def _px_to_world(self, px, py):
        lx = px / self.ppm - self._iw / 2
        ly = py / self.ppm - self._id / 2
        return (self._c[0] + lx * self._lat[0] + ly * self._fwd[0],
                self._c[1] + lx * self._lat[1] + ly * self._fwd[1])

    def _on_deck(self, wx, wz, thresh=0.6):
        px, py = self.to_px(wx, wz)
        xi, yi = int(px), int(py)
        if not (0 <= xi < self.gw and 0 <= yi < self.gh):
            return False
        return self.mask[yi, xi] > thresh

    def _interior_pts(self, margin_m):
        """Candidate points at least margin_m (diamond metric) inside the lit
        deck AND off the image border — content clipped by the projection edge
        reads as broken, so the canvas border erodes like a deck edge."""
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

    def _fresh_tracks(self):
        return [t for t in self.tracks.values() if self.t - t.last < TRACK_STALE_S]

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
        self._step_theme(dt)

    # ---- output ----
    def _heat_field(self):
        # memoized on engine time: render() and the sim's stream may both ask
        # within one tick, and blob adds must not double up
        if self._heat_t == self.t:
            return self._heat
        self._heat_t = self.t
        h = sum(w * o.sample() for w, o in zip(self._oct_w, self._octaves))
        # gamma via exact sqrt identities where possible — np.power was ~4x
        # slower on the Pi (1.5 = h*sqrt(h); 1.25 = h*sqrt(sqrt(h)))
        g = self.FIELD_GAMMA
        if g == 1.5:
            h *= np.sqrt(h)
        elif g == 1.25:
            h *= np.sqrt(np.sqrt(h))
        elif g != 1.0:
            h = h ** g
        self._field_blobs(h)
        np.clip(h, 0.0, 1.0, out=h)
        self._heat = h
        return h

    def _add_blob(self, h, px, py, r, amount, ring=False):
        if r >= 6.0:
            # big soft blobs come from a cached sprite, center snapped to the
            # pixel grid (invisible at these radii; the fresh mgrid+exp per
            # call was a measurable slice of the Pi frame)
            key = (round(r * 2) / 2.0, ring)
            g = self._stamps.get(key)
            if g is None:
                rr = key[0]
                ax = np.arange(-int(2 * rr), int(2 * rr) + 1, dtype=np.float32)
                d = np.hypot(ax[:, None], ax[None, :])
                g = (np.exp(-((d - rr) / (rr * 0.35)) ** 2) if ring
                     else np.exp(-(d / rr) ** 2)).astype(np.float32)
                if len(self._stamps) > 96:
                    self._stamps.clear()
                self._stamps[key] = g
            n = g.shape[0] // 2
            cx, cy = int(round(px)), int(round(py))
            x0, y0 = cx - n, cy - n
            sx0, sy0 = max(0, -x0), max(0, -y0)
            x0, y0 = max(0, x0), max(0, y0)
            x1 = min(self.gw, cx + n + 1)
            y1 = min(self.gh, cy + n + 1)
            if x1 > x0 and y1 > y0:
                h[y0:y1, x0:x1] += amount * g[sy0:sy0 + y1 - y0, sx0:sx0 + x1 - x0]
            return
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
        """uint8 (gh, gw, 3) frame: field through the palette, theme entities
        on top, deck mask + fade applied. Off-deck pixels stay black — the
        mask IS the projection mapping."""
        if self.fade <= 0:
            return np.zeros((self.gh, self.gw, 3), np.uint8)
        lut = lut if lut is not None else self.lut()
        heat = self._heat_field()
        if self._base is None:
            # the field IS the picture (lava): straight through the palette
            rgb = lut[(heat * 255).astype(np.uint8)].astype(np.float32)
        else:
            # textured floor: the palette is a LIGHT ramp multiplied over the
            # static base (sun dapple on leaves, torchlight on stone) — the
            # sim page mirrors this with a canvas multiply blend
            light = lut[(heat * 255).astype(np.uint8)].astype(np.float32)
            rgb = self._base * light
            rgb *= 1.0 / 255.0
        self._draw(rgb)
        np.clip(rgb, 0.0, 255.0, out=rgb)  # never let float sums wrap in uint8
        rgb *= self._env  # canopy dapple + deck mask, one precomposed pass
        if self.fade < 1.0:
            rgb *= self.fade
        return rgb.astype(np.uint8)

    # ---- patch toolbox ----
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

    def _build_island_patch(self, seed, edge_col=_ISLAND_EDGE, core_col=_ISLAND_CORE):
        """The mast base as a carved sun-stone altar: rock texture, two
        concentric carved rings, twelve tick marks, a center pit."""
        R = self.mast[2] + 0.06 * self.ppm
        col, alpha, _ = self._build_rock_patch(R, seed + 97, numeral=None,
                                               edge_col=edge_col,
                                               core_col=core_col)
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

    def _draw_island(self, rgb):
        col, alpha = self._island
        self._composite_patch(rgb, self.mast[0], self.mast[1], col, alpha)

    @staticmethod
    def _pack_patch(col, alpha):
        rgba = np.concatenate(
            [np.clip(col, 0, 255), alpha * 255], axis=2).astype(np.uint8)
        return {'w': rgba.shape[1], 'h': rgba.shape[0],
                'rgba': base64.b64encode(rgba.tobytes()).decode()}

    def heat_b64(self, step=2):
        """Downsampled scalar field for the sim stream (uint8, base64)."""
        if self.fade > 0:
            self._heat_field()
        return base64.b64encode(
            (self._heat[::step, ::step] * 255).astype(np.uint8).tobytes()).decode()

    def state(self, drain_events=True):
        st = {
            'fade': round(self.fade, 3),
            'active': self.active,
            'grid': [self.gw, self.gh],
            'tracks': [dict(zip(('x', 'y'),
                                map(lambda v: round(v, 1), self.to_px(t.x, t.z))))
                       for t in self.tracks.values()],
            'events': self.events if drain_events else list(self.events),
        }
        st.update(self._state_extra())
        if drain_events:
            self.events = []
        return st


class LavaShow(FloorShow):
    """Stepping stones on molten lava; Kukulkan lives underneath."""

    THEME = 'lava'
    PALETTE_STOPS = _PALETTE_STOPS
    OCTAVES = ((7, 0.055, 15), (17, 0.16, 205), (41, 0.55, 100))
    OCT_WEIGHTS = (0.55, 0.30, 0.15)
    FIELD_GAMMA = 1.5
    DAPPLE = DAPPLE_STRENGTH

    def _setup(self, seed):
        self._last_sink = -1e9
        self.bubbles = []
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

        # Kukulkan's head at MONSTER_ROT_STEPS orientations (the geometry is
        # analytic in heading-aligned coords, so each angle is built directly
        # — no image rotation). The sim page gets only the angle-0 patch and
        # rotates on canvas.
        self._heads = [self._build_head_patch(k * math.tau / MONSTER_ROT_STEPS)
                       for k in range(MONSTER_ROT_STEPS)]
        self._monster = {'mode': 'idle',
                         'next': self._rng.uniform(*MONSTER_FIRST_S),
                         'x': 0.0, 'y': 0.0, 'rot': 0.0, 't0': 0.0,
                         'dur': 0.0, 'sx': 0.0, 'sy': 0.0, 'glow': 0.0}

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

    # ---- simulation ----
    def _step_theme(self, dt):
        self._step_stones()
        self._step_mischief()
        self._step_bubbles(dt)
        self._step_embers(dt)
        self._step_glints(dt)
        self._step_monster(dt)

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
        fresh = self._fresh_tracks()
        for s in self.stones:
            if s.state != 'up' or not fresh:
                s.glint += (0.0 - s.glint) * k
                continue
            dmin = min(math.hypot(t.x - s.wx, t.z - s.wz) for t in fresh)
            target = np.clip(1.0 - (dmin - 0.35) / GLINT_R_M, 0.0, 1.0) * 0.55
            s.glint += (float(target) - s.glint) * k

    def _monster_spot(self):
        """Where to breach: on the lit deck, clear of stones and the altar,
        and — when walkers are tracked — visible but polite (~1.6 m away)."""
        pts = self._interior_pts(0.42)
        fresh = self._fresh_tracks()
        best, best_score = None, -1e9
        for _ in range(60):
            py, px = pts[self._rng.randrange(len(pts))]
            px, py = float(px), float(py)
            wx, wz = self._px_to_world(px, py)
            if any(s.state != 'down' and math.hypot(wx - s.wx, wz - s.wz) < 0.5
                   for s in self.stones):
                continue
            if math.hypot(px - self.mast[0], py - self.mast[1]) < \
                    self.mast[2] + (MONSTER_HEAD_L_M + 0.15) * self.ppm:
                continue
            if fresh:
                dmin = min(math.hypot(t.x - wx, t.z - wz) for t in fresh)
                if dmin < 0.9:
                    continue
                score = -abs(dmin - 1.6)
            else:
                score = self._rng.random()
            if score > best_score:
                best, best_score = (px, py), score
        return best

    def _step_monster(self, dt):
        m = self._monster
        if m['mode'] == 'idle':
            if self.fade > 0.5:
                m['next'] -= dt
                if m['next'] <= 0:
                    spot = self._monster_spot()
                    if spot is None:
                        m['next'] = 5.0
                        return
                    m['x'], m['y'] = spot
                    ang = self._rng.random() * math.tau
                    dist = self._rng.uniform(1.5, 2.5) * self.ppm
                    m['sx'] = m['x'] - math.cos(ang) * dist
                    m['sy'] = m['y'] - math.sin(ang) * dist
                    m['rot'] = ang
                    m['mode'] = 'swim'
                    m['t0'] = self.t
                    m['dur'] = self._rng.uniform(*MONSTER_SWIM_S)
                    self._emit({'e': 'monster_swim'})
            return
        if self.fade <= 0:  # show died mid-appearance: vanish quietly
            m['mode'] = 'idle'
            m['next'] = self._rng.uniform(*MONSTER_GAP_S)
            return
        ph = (self.t - m['t0']) / max(m['dur'], 1e-3)
        if m['mode'] == 'swim':
            if ph >= 1.0:
                m['mode'] = 'rise'
                m['t0'], m['dur'] = self.t, MONSTER_RISE_S
                self._emit({'e': 'monster_breach',
                            'x': round(m['x'], 1), 'y': round(m['y'], 1)})
                self._burst(m['x'], m['y'], 7)
        elif m['mode'] == 'rise':
            if ph >= 1.0:
                m['mode'] = 'hold'
                m['t0'], m['dur'] = self.t, self._rng.uniform(*MONSTER_HOLD_S)
        elif m['mode'] == 'hold':
            m['glow'] = 0.6 + 0.4 * math.sin(self.t * 4.2)
            if ph >= 1.0:
                m['mode'] = 'sink'
                m['t0'], m['dur'] = self.t, MONSTER_SINK_S
                self._emit({'e': 'monster_sink',
                            'x': round(m['x'], 1), 'y': round(m['y'], 1)})
                self._burst(m['x'], m['y'], 5)
        elif m['mode'] == 'sink' and ph >= 1.0:
            m['mode'] = 'idle'
            m['next'] = self._rng.uniform(*MONSTER_GAP_S)

    def _monster_pose(self):
        """(x, y, rot, scale) for the current mode, or None while hidden."""
        m = self._monster
        if m['mode'] in ('idle', 'swim'):
            return None
        ph = np.clip((self.t - m['t0']) / max(m['dur'], 1e-3), 0.0, 1.0)
        if m['mode'] == 'rise':
            scale = 0.3 + 0.7 * float(ph)
            rot = m['rot']
        elif m['mode'] == 'hold':
            scale = 1.0
            rot = m['rot'] + 0.44 * math.sin((self.t - m['t0']) / 3.4 * math.tau)
        else:  # sink
            scale = 1.0 - 0.75 * float(ph)
            rot = m['rot']
        return m['x'], m['y'], rot, scale

    # ---- output ----
    def _field_blobs(self, h):
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
        m = self._monster
        if m['mode'] == 'swim':
            # a dark mass moving under the crust, a faint bow-glow ahead of it
            ph = np.clip((self.t - m['t0']) / max(m['dur'], 1e-3), 0.0, 1.0)
            sway = 0.15 * self.ppm * math.sin(ph * math.tau * 1.5)
            ca, sa = math.cos(m['rot']), math.sin(m['rot'])
            x = m['sx'] + (m['x'] - m['sx']) * ph - sa * sway
            y = m['sy'] + (m['y'] - m['sy']) * ph + ca * sway
            self._add_blob(h, x, y, 0.30 * self.ppm, -0.4)
            self._add_blob(h, x + ca * 0.35 * self.ppm, y + sa * 0.35 * self.ppm,
                           0.14 * self.ppm, 0.25)
        elif m['mode'] in ('rise', 'hold', 'sink'):
            # displaced lava glows in a ring around the breach
            self._add_blob(h, m['x'], m['y'],
                           MONSTER_HEAD_L_M * 1.25 * self.ppm, 0.32, ring=True)

    def _draw(self, rgb):
        for s in self.stones:
            self._draw_stone(rgb, s)
        self._draw_island(rgb)
        pose = self._monster_pose()
        if pose is not None:
            x, y, rot, scale = pose
            k = int(round(rot / (math.tau / MONSTER_ROT_STEPS))) % MONSTER_ROT_STEPS
            col, alpha, eyes = self._heads[k]
            if scale != 1.0:
                col, alpha, eyes = _scale_patch(col, alpha, eyes, scale)
            show = col + eyes * self._monster['glow'] * (_EYE_AMBER - col) * 0.7
            self._composite_patch(rgb, x, y, col, alpha, show)

    def _build_head_patch(self, ang):
        """Kukulkan viewed from above: obsidian superellipse head pointing
        along `ang`, jade feather crest fanning off the back, two amber eyes
        (plus an eye mask so the pulse can be applied at composite time)."""
        L = MONSTER_HEAD_L_M * self.ppm
        W = MONSTER_HEAD_W_M * self.ppm
        pad = int(math.ceil(L * 1.95)) + 3  # room for the swept-back crest
        s = 2 * pad + 1
        ys, xs = np.mgrid[0:s, 0:s].astype(np.float32)
        dx, dy = xs - pad, ys - pad
        ca, sa = math.cos(ang), math.sin(ang)
        u = dx * ca + dy * sa
        v = -dx * sa + dy * ca
        rng = np.random.default_rng(4242)  # same skin at every angle
        # tapered snout: the head narrows toward +u, wide at the skull
        fw = W * (1.0 - 0.35 * np.clip(u / L, 0.0, 1.0))
        body = np.abs(u / L) ** 2.4 + np.abs(v / np.maximum(fw, 1e-3)) ** 2.4
        a_head = np.clip((1.0 - body) * 6.0, 0.0, 1.0)
        scales = 0.66 + 0.60 * _static_noise(rng, s, s, max(4, s // 5))
        shade = 0.70 + 0.30 * np.clip(1.4 - body * 1.4, 0.0, 1.0)
        col_head = _OBSIDIAN * (scales * shade)[..., None]
        ridge = np.clip(1.0 - np.abs(v) / (0.16 * W), 0.0, 1.0) * (u > -0.3 * L)
        col_head *= (1.0 + 0.22 * ridge)[..., None]
        # lava underlight: ember rim where the silhouette meets the melt
        band = np.clip((1.0 - body) * 6.0, 0.0, 1.0) - np.clip((1.0 - body) * 2.2, 0.0, 1.0)
        col_head = col_head + band[..., None] * (_EMBER_RIM - col_head) * 0.45
        # crest: seven long feathers swept backward off the skull,
        # alternating jade shades so they separate
        a_crest = np.zeros((s, s), np.float32)
        col_crest = np.zeros((s, s, 3), np.float32)
        for k in range(-3, 4):
            cu = -(0.95 + 0.17 * abs(k)) * L
            cv = k * 0.30 * W
            lobe = ((u - cu) / (0.55 * W)) ** 2 + ((v - cv) / (0.20 * W)) ** 2
            a_l = np.clip((1.0 - lobe) * 4.0, 0.0, 1.0)
            shade_l = 0.70 + 0.30 * ((k + 3) % 2)
            col_crest = np.where(a_l[..., None] > a_crest[..., None],
                                 _JADE * shade_l, col_crest)
            a_crest = np.maximum(a_crest, a_l)
        # eyes: forward, wide-set, white-hot cores; mask kept for the pulse
        eye_mask = np.zeros((s, s), np.float32)
        core_mask = np.zeros((s, s), np.float32)
        for sv in (-1, 1):
            de = np.hypot(u - 0.46 * L, v - sv * 0.42 * W)
            eye_mask = np.maximum(eye_mask, np.clip((0.19 * W - de) / 1.2, 0.0, 1.0))
            core_mask = np.maximum(core_mask, np.clip((0.09 * W - de) / 1.0, 0.0, 1.0))
        alpha = np.maximum(a_head, a_crest * 0.92)[..., None]
        col = np.where(a_head[..., None] > 0.4, col_head, col_crest)
        col = col + eye_mask[..., None] * (_EYE_AMBER - col) * 0.9
        col = col + core_mask[..., None] * (_EYE_CORE - col)
        return (col.astype(np.float32), alpha.astype(np.float32),
                eye_mask[..., None].astype(np.float32))

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

    def hello_patches(self):
        """The precomputed rock artwork for the sim page (one-time, hello
        message): every stone plus the altar as raw RGBA — the browser draws
        the SAME pixels production projects, no second texture implementation."""
        stones = []
        for s in self.stones:
            col, alpha, _ = self._patches[s.sid]
            stones.append({'id': s.sid, **self._pack_patch(col, alpha)})
        icol, ialpha = self._island
        island = {'x': round(self.mast[0], 1), 'y': round(self.mast[1], 1),
                  **self._pack_patch(icol, ialpha)}
        hcol, halpha, _ = self._heads[0]  # angle 0 = pointing +x; page rotates
        return {'stones': stones, 'island': island,
                'monster': self._pack_patch(hcol, halpha)}

    def _state_extra(self):
        return {
            'stones': [{'id': s.sid, 'x': round(s.px, 1), 'y': round(s.py, 1),
                        'r': round(STONE_R_M * self.ppm, 1), 'state': s.state,
                        'phase': round(s.phase(self.t), 3),
                        'glint': round(s.glint, 2)} for s in self.stones],
            'monster': (lambda p: p and {
                'x': round(p[0], 1), 'y': round(p[1], 1),
                'rot': round(p[2], 3), 'scale': round(p[3], 3),
                'mode': self._monster['mode'],
                'glow': round(self._monster['glow'], 2)})(self._monster_pose()),
        }


class JungleShow(FloorShow):
    """The temple floor the jungle took back: sun-dappled undergrowth, snakes
    that slither across and dart away from feet, fallen glyph stones going
    mossy, fireflies, and a sun-pool over each walker."""

    THEME = 'jungle'
    PALETTE_STOPS = _JUNGLE_STOPS
    OCTAVES = ((7, 0.028, 200), (17, 0.075, 40), (41, 0.22, 140))
    OCT_WEIGHTS = (0.50, 0.32, 0.18)
    FIELD_GAMMA = 1.25   # sqrt-identity fast path (was 1.3 — imperceptible)
    DAPPLE = 0.30

    def _setup(self, seed):
        self._pole_clear = self.mast[2] / self.ppm + 0.22

        # fallen glyph stones, half-swallowed by moss (decorative ruins —
        # dots-and-bars carvings, NOT the lava chain's wayfinding numerals)
        pts = self._interior_pts(GLYPH_R_M + 0.15)
        self.glyphs = []
        numerals = (4, 8, 13)
        for _ in range(240):
            if len(self.glyphs) >= GLYPH_N:
                break
            py, px = pts[self._rng.randrange(len(pts))]
            px, py = float(px), float(py)
            if math.hypot(px - self.mast[0], py - self.mast[1]) < self.mast[2] + 0.55 * self.ppm:
                continue
            if any(math.hypot(px - g['px'], py - g['py']) < 1.0 * self.ppm
                   for g in self.glyphs):
                continue
            i = len(self.glyphs)
            col, alpha, carve = self._build_rock_patch(
                GLYPH_R_M * self.ppm, seed + 31 * (i + 1), numeral=numerals[i],
                heading=self._rng.random() * math.tau,
                edge_col=_MOSS_EDGE, core_col=_MOSS_CORE)
            self._mossify(col, seed + 61 * (i + 1))
            wx, wz = self._px_to_world(px, py)
            self.glyphs.append({'gid': i, 'wx': wx, 'wz': wz, 'px': px, 'py': py,
                                'col': col, 'alpha': alpha, 'carve': carve,
                                'glint': 0.0})

        self._island = self._build_island_patch(
            seed, edge_col=np.array([44, 56, 40], np.float32),
            core_col=np.array([88, 98, 76], np.float32))

        # snakes: spawn spread out, each with its own gait
        self.snakes = []
        spawn_pts = self._interior_pts(0.30)
        for i, spec in enumerate(SNAKE_SPECS):
            for _ in range(60):
                py, px = spawn_pts[self._rng.randrange(len(spawn_pts))]
                wx, wz = self._px_to_world(float(px), float(py))
                if math.hypot(wx - self._cx, wz - self._cz) < self._pole_clear + 0.3:
                    continue
                if any(math.hypot(wx - o.x, wz - o.z) < 0.8 for o in self.snakes):
                    continue
                break
            sn = _Snake(i, spec['kind'], wx, wz,
                        self._rng.random() * math.tau,
                        self._rng.uniform(*SNAKE_SPEED),
                        max(6, round(spec['len_m'] / SNAKE_SEG_M)),
                        (self._rng.uniform(*SNAKE_WEAVE),
                         self._rng.uniform(*SNAKE_WEAVE_HZ),
                         self._rng.random() * math.tau))
            sn.tongue_t = self._rng.uniform(*TONGUE_GAP_S)
            sn.style = self._snake_style(
                spec, sn.n_seg, np.random.default_rng(seed + 101 + 7 * i))
            self.snakes.append(sn)

        # parted-grass glow wake the snakes leave in the field
        self._wake = np.zeros((self.gh, self.gw), np.float32)

        self.flies = []

        # the floor itself: a leaf-litter carpet, painted once (Tim's pick
        # 2026-07-23 from the four-way background comparison); the moving
        # light field multiplies over it in render()
        self._base = self._leaf_base(seed + 7)

    def _leaf_base(self, seed):
        """The jungle floor: ~soil under a carpet of overlapping leaves —
        greens, olives, rusts — stamped once at init (count scales with grid
        area so every resolution gets the same density)."""
        rng = np.random.default_rng(seed)
        base = np.empty((self.gh, self.gw, 3), np.float32)
        base[:] = (22, 25, 14)
        cols = np.array([[30, 58, 24], [44, 84, 30], [70, 88, 32],
                         [88, 68, 34], [96, 56, 28], [52, 74, 26]], np.float32)
        scale = self.ppm / 82.3   # leaf size in meters, not pixels
        for _ in range(int(LEAF_DENSITY * self.gw * self.gh)):
            cx, cy = rng.uniform(0, self.gw), rng.uniform(0, self.gh)
            ang = rng.uniform(0, math.tau)
            length = rng.uniform(4.5, 8.5) * scale
            width = length * rng.uniform(0.32, 0.50)
            c = cols[rng.integers(len(cols))] * rng.uniform(0.72, 1.15)
            pad = int(length) + 2
            ys, xs = np.mgrid[-pad:pad + 1, -pad:pad + 1].astype(np.float32)
            ca, sa = math.cos(ang), math.sin(ang)
            u, v = xs * ca + ys * sa, -xs * sa + ys * ca
            ell = (u / length) ** 2 + (v / max(width, 1e-3)) ** 2
            a = np.clip((1 - ell) * 3.0, 0, 1)[..., None]
            vein = np.clip(1 - np.abs(v) / 0.7, 0, 1) * (np.abs(u) < length * 0.8)
            col = c * (0.70 + 0.5 * np.clip(1 - ell, 0, 1))[..., None]
            col = col * (1 - 0.25 * vein[..., None])
            x0, y0 = int(cx) - pad, int(cy) - pad
            sx0, sy0 = max(0, -x0), max(0, -y0)
            x0c, y0c = max(0, x0), max(0, y0)
            x1 = min(self.gw, x0 + 2 * pad + 1)
            y1 = min(self.gh, y0 + 2 * pad + 1)
            if x1 <= x0c or y1 <= y0c:
                continue
            aa = a[sy0:sy0 + y1 - y0c, sx0:sx0 + x1 - x0c]
            cc = col[sy0:sy0 + y1 - y0c, sx0:sx0 + x1 - x0c]
            region = base[y0c:y1, x0c:x1]
            region[:] = region * (1 - aa) + cc * aa
        return base

    @staticmethod
    def _mossify(col, seed):
        """Moss eats a rock patch from the rim inward: kill red/blue, keep
        green, in noise-broken blotches over the outer half."""
        s = col.shape[0]
        pad = s // 2
        ys, xs = np.mgrid[0:s, 0:s].astype(np.float32)
        d = np.hypot(xs - pad, ys - pad) / max(pad, 1)
        band = np.clip((d - 0.30) / 0.45, 0.0, 1.0)
        moss = _static_noise(np.random.default_rng(seed), s, s, 5)
        eat = band * np.clip(moss * 1.7 - 0.20, 0.0, 1.0)
        col *= 1.0 - eat[..., None] * np.array([0.58, 0.10, 0.62], np.float32)

    def _snake_style(self, spec, n, rng):
        """The snake's whole look, precomputed: a silhouette width profile
        (spade head → jaw flare → neck pinch → body → tail; the rattler's
        tail ends in a held-wide segmented rattle instead of a point) as
        np.interp knots over arc length, the skin pattern (rattler: brown
        diamond chain on sandy tan + buff keratin rings; gold: bright gold
        with fleck speckle; coral: red/yellow/black rings, black snout),
        slow per-arc brightness variation, and a scale-speckle table.
        Per-INDEX colors + half-widths (spine samples are SNAKE_SEG_M apart)
        ship to the sim page so both displays draw the same body."""
        kind = spec['kind']
        w = spec['r_m'] * self.ppm
        seg = SNAKE_SEG_M * self.ppm
        total = (n - 1) * seg
        head = SNAKE_HEAD_X * w
        rat = RATTLE_M * self.ppm
        ring = RATTLE_RING_M * self.ppm
        if kind == 'rattler':
            xp = np.array([0.0, 0.28 * head, 0.62 * head, 1.05 * head,
                           1.5 * head, 0.60 * total, 0.80 * total,
                           total - rat, total - 0.8 * rat, total], np.float32)
            fp = np.array([0.26, 1.30, 1.38, 0.74, 1.00,
                           1.00, 0.60, 0.30, 0.40, 0.30], np.float32)
        else:
            xp = np.array([0.0, 0.28 * head, 0.62 * head, 1.05 * head,
                           1.5 * head, 0.60 * total, 0.78 * total,
                           0.92 * total, total], np.float32)
            fp = np.array([0.26, 1.30, 1.38, 0.74, 1.00,
                           1.00, 0.72, 0.38, 0.10], np.float32)
        arcs = np.arange(n, dtype=np.float32) * seg
        var = (0.90 + 0.20 * rng.random(n)).astype(np.float32)
        per = (SNAKE_DIAMOND_PER_M if kind == 'rattler'
               else SNAKE_CORAL_PER_M) * self.ppm

        def color_at(a, v):
            """Spine-center color at arc a (page approximation of the 2-D
            pattern: diamonds read as dark bands there)."""
            if kind == 'rattler':
                if a > total - rat:
                    return (_RTL_RING_B if int((total - a) / ring) % 2
                            else _RTL_RING_A)
                if a < head * 0.9:
                    return _RTL_BASE * 0.72
                fr = abs(((a / per) % 1.0) - 0.5) * 2.0
                return (_RTL_DARK if fr < 0.63 else _RTL_BASE) * v
            if kind == 'gold':
                if a < head * 0.9:
                    return _GOLD_BASE * 0.85
                return _GOLD_BASE * v
            if a < head * 1.1:
                return _CORAL_K
            u = (a / per) % 1.0
            if u < 0.40:
                c = _CORAL_R
            elif u < 0.52 or u >= 0.88:
                c = _CORAL_Y
            else:
                c = _CORAL_K
            return c * min(1.1, v + 0.04)

        cols_idx = [color_at(float(a), float(v)) for a, v in zip(arcs, var)]
        w_idx = w * np.interp(arcs, xp, fp)
        spread = 0.30 if kind == 'gold' else 0.20  # gold flecks harder
        return {'w': w, 'head': head, 'per': per, 'seg': seg, 'total': total,
                'rat': rat, 'ring': ring,
                'eye': _EYE_DARK if kind == 'gold' else _SNAKE_EYE,
                'xp': xp, 'fp': fp, 'arcs': arcs, 'var': var,
                'spec1d': (1.0 - spread / 2
                           + spread * rng.random(64)).astype(np.float32),
                'cols_idx': cols_idx, 'w_idx': w_idx.astype(np.float32)}

    # ---- simulation ----
    def _step_theme(self, dt):
        self._step_snakes(dt)
        self._step_flies(dt)
        self._step_glyph_glints(dt)

    def _snake_goal(self, sn):
        """Somewhere across the deck: interior, off the mast, not underfoot."""
        pts = self._interior_pts(0.30)
        fresh = self._fresh_tracks()
        for _ in range(40):
            py, px = pts[self._rng.randrange(len(pts))]
            wx, wz = self._px_to_world(float(px), float(py))
            if math.hypot(wx - sn.x, wz - sn.z) < 1.0:
                continue
            if math.hypot(wx - self._cx, wz - self._cz) < self._pole_clear + 0.25:
                continue
            if any(math.hypot(wx - t.x, wz - t.z) < 0.8 for t in fresh):
                continue
            return (wx, wz)
        return (self._cx + 0.8, self._cz)

    def _step_snakes(self, dt):
        self._wake *= math.exp(-dt / WAKE_TAU_S)
        fresh = self._fresh_tracks()
        for sn in self.snakes:
            if (sn.goal is None or self.t - sn.goal_t > SNAKE_GOAL_S
                    or math.hypot(sn.goal[0] - sn.x, sn.goal[1] - sn.z) < 0.30):
                sn.goal = self._snake_goal(sn)
                sn.goal_t = self.t
            steer = SNAKE_TURN * _angdiff(
                math.atan2(sn.goal[1] - sn.z, sn.goal[0] - sn.x), sn.heading)
            # feet nearby: drop everything and get away. Hysteresis (spooked
            # inside R, calm again only past R*SNAKE_CALM_X) plus a per-snake
            # event cooldown, or the boundary jitter spams the event log.
            fleeing = False
            if fresh:
                tn = min(fresh, key=lambda t: math.hypot(t.x - sn.x, t.z - sn.z))
                d_feet = math.hypot(tn.x - sn.x, tn.z - sn.z)
                if d_feet < SNAKE_FLEE_R_M * (SNAKE_CALM_X if sn.flee else 1.0):
                    fleeing = True
                    steer = 4.5 * _angdiff(
                        math.atan2(sn.z - tn.z, sn.x - tn.x), sn.heading)
            if fleeing and not sn.flee:
                sn.goal = None  # after the scare, pick somewhere new to go
                if self.t - sn.flee_ev > SNAKE_FLEE_EV_GAP_S:
                    sn.flee_ev = self.t
                    px, py = self.to_px(sn.x, sn.z)
                    self._emit({'e': 'snake_flee', 'id': sn.sid,
                                'x': round(px, 1), 'y': round(py, 1)})
            sn.flee = fleeing
            # the mast is real; slither around it
            dm = math.hypot(sn.x - self._cx, sn.z - self._cz)
            if dm < self._pole_clear + 0.15:
                steer += 4.0 * _angdiff(
                    math.atan2(sn.z - self._cz, sn.x - self._cx), sn.heading)
            # deck edge lookahead: turn back toward the middle
            la = (sn.x + math.cos(sn.heading) * 0.30,
                  sn.z + math.sin(sn.heading) * 0.30)
            weave = sn.weave_a * math.sin(self.t * sn.weave_hz * math.tau + sn.weave_ph)
            if not self._on_deck(*la):
                steer = 5.0 * _angdiff(
                    math.atan2(self._cz - sn.z, self._cx - sn.x), sn.heading)
                weave = 0.0
            sn.heading += (max(-5.0, min(5.0, steer)) + weave) * dt
            # burst-and-glide gait: speed swells with the weave phase
            pulse = 0.72 + 0.56 * abs(math.sin(
                self.t * sn.weave_hz * math.tau + sn.weave_ph))
            want = SNAKE_FLEE_SPEED if fleeing else sn.speed * pulse
            sn.spd += (want - sn.spd) * min(1.0, 3.0 * dt)
            sn.x += math.cos(sn.heading) * sn.spd * dt
            sn.z += math.sin(sn.heading) * sn.spd * dt
            # spine trail: slot 0 mirrors the live head; a new point is laid
            # down each time the head gets a full segment ahead
            sn.trail[0] = (sn.x, sn.z)
            if len(sn.trail) < 2 or math.hypot(
                    sn.trail[0][0] - sn.trail[1][0],
                    sn.trail[0][1] - sn.trail[1][1]) >= SNAKE_SEG_M:
                sn.trail.insert(0, (sn.x, sn.z))
                del sn.trail[sn.n_seg:]
            # tongue flicks
            sn.tongue_t -= dt
            if sn.tongue_t <= 0:
                sn.tongue_on = not sn.tongue_on
                sn.tongue_t = (TONGUE_FLICK_S if sn.tongue_on
                               else self._rng.uniform(*TONGUE_GAP_S))
            if self.fade > 0:
                px, py = self.to_px(sn.x, sn.z)
                self._add_blob(self._wake, px, py, 0.07 * self.ppm, WAKE_DEP * dt)

    def _step_flies(self, dt):
        if (self.fade > 0 and len(self.flies) < FIREFLY_N
                and self._rng.random() < 0.7 * dt * self.fade):
            py, px = self._mask_pts[self._rng.randrange(len(self._mask_pts))]
            a = self._rng.random() * math.tau
            sp = self._rng.uniform(0.03, 0.07) * self.ppm
            self.flies.append({'x': float(px), 'y': float(py),
                               'vx': math.cos(a) * sp, 'vy': math.sin(a) * sp,
                               't0': self.t, 'life': self._rng.uniform(*FIREFLY_LIFE_S),
                               'on': False, 'sw': self._rng.uniform(0.5, 2.0)})
        alive = []
        for f in self.flies:
            if self.t - f['t0'] >= f['life']:
                continue
            turn = self._rng.uniform(-1.0, 1.0) * 1.6 * dt
            ca, sa = math.cos(turn), math.sin(turn)
            f['vx'], f['vy'] = f['vx'] * ca - f['vy'] * sa, f['vx'] * sa + f['vy'] * ca
            f['x'] += f['vx'] * dt
            f['y'] += f['vy'] * dt
            xi, yi = int(f['x']), int(f['y'])
            if not (0 <= xi < self.gw and 0 <= yi < self.gh) or self.mask[yi, xi] < 0.5:
                sp = math.hypot(f['vx'], f['vy'])
                d = math.hypot(self.mast[0] - f['x'], self.mast[1] - f['y']) or 1.0
                f['vx'] = (self.mast[0] - f['x']) / d * sp
                f['vy'] = (self.mast[1] - f['y']) / d * sp
            f['sw'] -= dt
            if f['sw'] <= 0:
                f['on'] = not f['on']
                f['sw'] = (self._rng.uniform(0.45, 0.9) if f['on']
                           else self._rng.uniform(0.9, 2.6))
            alive.append(f)
        self.flies = alive

    def _step_glyph_glints(self, dt):
        # a carved stone notices an approaching walker (same idea as the
        # lava chain's numerals, mossier color)
        k = min(1.0, dt * 6.0)
        fresh = self._fresh_tracks()
        for g in self.glyphs:
            if not fresh:
                g['glint'] += (0.0 - g['glint']) * k
                continue
            dmin = min(math.hypot(t.x - g['wx'], t.z - g['wz']) for t in fresh)
            target = np.clip(1.0 - (dmin - 0.35) / GLINT_R_M, 0.0, 1.0) * 0.55
            g['glint'] += (float(target) - g['glint']) * k

    # ---- output ----
    def _field_blobs(self, h):
        h += self._wake
        for t in self.tracks.values():
            if self.t - t.last < TRACK_STALE_S:
                px, py = self.to_px(t.x, t.z)
                self._add_blob(h, px, py, SUN_R_M * self.ppm, SUN_AMOUNT)
        for f in self.flies:
            if f['on']:
                self._add_blob(h, f['x'], f['y'], 2.2, 0.55)

    def _draw(self, rgb):
        for g in self.glyphs:
            show = None
            if g['glint'] > 0.02:
                gm = (g['carve'] * g['glint'])[..., None]
                show = g['col'] + gm * (_MOSS_GLINT - g['col']) * 0.8
            self._composite_patch(rgb, g['px'], g['py'], g['col'], g['alpha'], show)
        self._draw_island(rgb)
        for sn in self.snakes:
            self._draw_snake(rgb, sn)
        for f in self.flies:
            if f['on']:
                self._dot(rgb, f['x'], f['y'], 1.1, _FLY_CORE)

    def _dot(self, rgb, px, py, r, col):
        x0, x1 = max(0, int(px - r) - 1), min(self.gw, int(px + r) + 2)
        y0, y1 = max(0, int(py - r) - 1), min(self.gh, int(py + r) + 2)
        if x1 <= x0 or y1 <= y0:
            return
        ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        a = np.clip((r - np.hypot(xs - px, ys - py)) / 0.8, 0.0, 1.0)[..., None]
        region = rgb[y0:y1, x0:x1]
        region[:] = region * (1 - a) + col * a

    def _draw_snake(self, rgb, sn):
        """One smooth body, not beads: a distance field to the spine polyline
        over the snake's bounding box, carrying the arc length of the nearest
        spine point. Width-by-arc gives the silhouette (spade head, neck,
        tail taper); arc drives the skin pattern; distance/width gives the
        rounded-body shading. ~30 small-array segment passes per snake."""
        st = sn.style
        pts = [self.to_px(*p) for p in sn.trail]
        n = len(pts)
        if n < 2:
            return
        # distance field runs on every THIRD spine point (chord error at this
        # curvature < 0.5 px — invisible; cuts the segment count for the Pi)
        fpts = pts[::3]
        if fpts[-1] != pts[-1]:
            fpts.append(pts[-1])
        wmax = st['w'] * 1.5
        x0 = max(0, int(min(p[0] for p in pts) - wmax) - 2)
        x1 = min(self.gw, int(max(p[0] for p in pts) + wmax) + 3)
        y0 = max(0, int(min(p[1] for p in pts) - wmax) - 2)
        y1 = min(self.gh, int(max(p[1] for p in pts) + wmax) + 3)
        if x1 <= x0 or y1 <= y0:
            return
        lat = SNAKE_FIELD_STEP
        ys, xs = np.mgrid[y0:y1:lat, x0:x1:lat].astype(np.float32)
        # one broadcast pass over all segments at once — a python loop of
        # small per-segment array ops drowned in numpy call overhead on the
        # Pi (~46 ms/snake); batched it's a handful of (S,H,W) ops on a
        # half-res lattice (coords stay in full-res px, so style math holds)
        fp_a = np.asarray(fpts, np.float32)
        va = fp_a[1:] - fp_a[:-1]
        l2 = (va * va).sum(1)
        keep = l2 > 1e-6
        aa, va, l2 = fp_a[:-1][keep], va[keep], l2[keep]
        if not len(aa):
            return
        seg_l = np.sqrt(l2)
        cum0 = np.concatenate(([0.0], np.cumsum(seg_l))).astype(np.float32)
        gx = xs[None] - aa[:, 0, None, None]
        gy = ys[None] - aa[:, 1, None, None]
        t = np.clip((gx * va[:, 0, None, None] + gy * va[:, 1, None, None])
                    / l2[:, None, None], 0.0, 1.0)
        gx -= t * va[:, 0, None, None]
        gy -= t * va[:, 1, None, None]
        d2 = gx * gx + gy * gy
        k = np.argmin(d2, 0)[None]
        dmin = np.sqrt(np.take_along_axis(d2, k, 0)[0])
        tarc = (cum0[k[0]] + np.take_along_axis(t, k, 0)[0] * seg_l[k[0]])
        # full-resolution cumulative arc for feature placement (eyes)
        cum = [0.0]
        for i in range(n - 1):
            cum.append(cum[-1] + math.hypot(pts[i + 1][0] - pts[i][0],
                                            pts[i + 1][1] - pts[i][1]))
        # pattern + shading at LATTICE res (color detail hides inside the
        # smooth silhouette; the silhouette itself is evaluated full-res)
        w_l = st['w'] * np.interp(tarc, st['xp'], st['fp']).astype(np.float32)
        rel = np.clip(dmin / np.maximum(w_l, 1e-3), 0.0, 1.0)
        var = np.interp(tarc, st['arcs'], st['var']).astype(np.float32)
        if sn.kind == 'rattler':
            fr = np.abs(((tarc / st['per']) % 1.0) - 0.5) * 2.0
            diamond = rel < np.clip(0.95 - fr * 1.5, 0.0, 1.0) * 0.9
            col = np.where(diamond[..., None], _RTL_DARK, _RTL_BASE * var[..., None])
            # pale flank line under the diamonds (triangle band)
            stripe = np.clip(1.0 - np.abs(rel - 0.62) / 0.20, 0.0, 1.0) * 0.22
            col = col * (1.0 + stripe[..., None])
            col = np.where((tarc < st['head'] * 0.9)[..., None], _RTL_BASE * 0.72, col)
            # the rattle: alternating keratin rings; buzzes while fleeing
            zone = tarc > st['total'] - st['rat']
            if zone.any():
                seg_i = ((st['total'] - tarc) / st['ring']).astype(np.int32) % 2
                rcol = np.where(seg_i[..., None] > 0, _RTL_RING_B, _RTL_RING_A)
                if sn.flee:
                    rcol = rcol * (1.05 + 0.45 * math.sin(self.t * 50.0))
                col = np.where(zone[..., None], rcol, col)
        elif sn.kind == 'gold':
            col = _GOLD_BASE * var[..., None]
            # faint darker dorsal line down the spine
            col = col * (1.0 - 0.12 * np.clip(1.0 - rel / 0.25, 0.0, 1.0))[..., None]
            col = np.where((tarc < st['head'] * 0.9)[..., None], _GOLD_BASE * 0.85, col)
        else:
            u = (tarc / st['per']) % 1.0
            col = np.where((u < 0.40)[..., None], _CORAL_R,
                           np.where(((u < 0.52) | (u >= 0.88))[..., None],
                                    _CORAL_Y, _CORAL_K)) * np.minimum(
                1.1, var + 0.04)[..., None]
            col = np.where((tarc < st['head'] * 1.1)[..., None], _CORAL_K, col)
        # rounded body: dorsal highlight to edge falloff, plus scale speckle
        # (1-D lengthwise bands — the 2-D bilerp was gather-bound on the Pi)
        spec = st['spec1d'][(tarc * 0.55).astype(np.int32) % 64]
        shade = (0.70 + 0.40 * np.sqrt(np.clip(1.0 - rel * rel, 0.0, 1.0))) * spec
        col = col * shade[..., None]
        if lat > 1:
            # distance and arc are smooth — bilinear-upsample THEM and redo
            # only the silhouette at full res (upsampling alpha instead made
            # the tail fragment; nearest-upsampling color is invisible)
            dmin = _up2(dmin, y1 - y0, x1 - x0)
            tarc = _up2(tarc, y1 - y0, x1 - x0)
            col = col.repeat(lat, 0).repeat(lat, 1)[:y1 - y0, :x1 - x0]
        w = st['w'] * np.interp(tarc, st['xp'], st['fp']).astype(np.float32)
        body = np.clip((w - dmin) / 1.2, 0.0, 1.0)
        if body.max() <= 0:
            return
        a = body[..., None]
        region = rgb[y0:y1, x0:x1]
        region[:] = region * (1 - a) + col * a

        # eyes on the sides of the spade, tongue off the snout tip
        exy = self._spine_at(pts, cum, st['head'] * 0.42)
        if exy is not None:
            px, py, tx, ty = exy
            off = 0.72 * st['w']
            for sv in (-1, 1):
                self._dot(rgb, px - ty * sv * off, py + tx * sv * off,
                          1.15, st['eye'])
        if sn.tongue_on:
            hx, hy = pts[0]
            p1 = pts[1]
            ang = math.atan2(hy - p1[1], hx - p1[0])
            ca, sa = math.cos(ang), math.sin(ang)
            tip = st['w'] * 0.35
            for sv in (-1, 1):
                self._dot(rgb, hx + ca * (tip + 2.6) - sa * sv * 1.1,
                          hy + sa * (tip + 2.6) + ca * sv * 1.1, 0.9, _TONGUE)
            self._dot(rgb, hx + ca * (tip + 1.3), hy + sa * (tip + 1.3), 0.9, _TONGUE)

    @staticmethod
    def _spine_at(pts, cum, a):
        """Point + unit tangent on the pts polyline at arc distance a."""
        for i in range(len(cum) - 1):
            if cum[i + 1] >= a or i == len(cum) - 2:
                seg = (cum[i + 1] - cum[i]) or 1e-6
                f = min(1.0, max(0.0, (a - cum[i]) / seg))
                ax, ay = pts[i]
                bx, by = pts[i + 1]
                return (ax + (bx - ax) * f, ay + (by - ay) * f,
                        (bx - ax) / seg, (by - ay) / seg)
        return None

    def hello_patches(self):
        """Precomputed jungle artwork for the sim page: the mossy altar, the
        glyph stones, and each snake's per-index colors + widths so the page
        draws the same body the production rasterizer does."""
        icol, ialpha = self._island
        glyphs = [{'id': g['gid'], 'x': round(g['px'], 1), 'y': round(g['py'], 1),
                   **self._pack_patch(g['col'], g['alpha'])} for g in self.glyphs]
        ones = np.ones(self._base.shape[:2] + (1,), np.float32)
        return {'base': self._pack_patch(self._base, ones),
                'island': {'x': round(self.mast[0], 1), 'y': round(self.mast[1], 1),
                           **self._pack_patch(icol, ialpha)},
                'glyphs': glyphs,
                'snakes': [{'id': sn.sid, 'kind': sn.kind,
                            'colors': [[int(c[0]), int(c[1]), int(c[2])]
                                       for c in sn.style['cols_idx']],
                            'w': [round(float(v), 2) for v in sn.style['w_idx']]}
                           for sn in self.snakes]}

    def _state_extra(self):
        return {
            'snakes': [{'id': sn.sid, 'tongue': 1 if sn.tongue_on else 0,
                        'flee': 1 if sn.flee else 0,
                        'pts': [[round(px, 1), round(py, 1)]
                                for px, py in (self.to_px(*p) for p in sn.trail)]}
                       for sn in self.snakes],
            'flies': [{'x': round(f['x'], 1), 'y': round(f['y'], 1)}
                      for f in self.flies if f['on']],
            'glyphs': [{'id': g['gid'], 'glint': round(g['glint'], 2)}
                       for g in self.glyphs],
        }


class TempleShow(FloorShow):
    """The temple floor itself, swept and torch-lit: dark weathered
    flagstones with moss veining the joints, a few flags carrying carved
    glyphs that glint gold as a walker approaches, dust motes drifting
    through the light, torch flicker breathing over everything, and a warm
    light-pool following each walker. The calm show of the three."""

    THEME = 'temple'
    PALETTE_STOPS = _TEMPLE_STOPS
    OCTAVES = ((7, 0.024, 100), (17, 0.06, 300), (41, 0.18, 40))
    OCT_WEIGHTS = (0.50, 0.32, 0.18)
    FIELD_GAMMA = 1.25
    DAPPLE = 0.18

    def _setup(self, seed):
        self._base = self._flag_base(seed + 3)

        # carved flags: glyphs cut INTO the floor texture; each keeps its
        # carve mask so the gold glint can composite over it on approach
        pts = self._interior_pts(0.35)
        self.glyphs = []
        numerals = (0, 7, 12)  # shell glyph + dots-and-bars
        for _ in range(240):
            if len(self.glyphs) >= CARVED_FLAGS:
                break
            py, px = pts[self._rng.randrange(len(pts))]
            px, py = float(px), float(py)
            if math.hypot(px - self.mast[0], py - self.mast[1]) < self.mast[2] + 0.55 * self.ppm:
                continue
            if any(math.hypot(px - g['px'], py - g['py']) < 1.0 * self.ppm
                   for g in self.glyphs):
                continue
            i = len(self.glyphs)
            r = 0.17 * self.ppm
            pad = int(math.ceil(r * 1.2)) + 2
            s = 2 * pad + 1
            ys, xs = np.mgrid[0:s, 0:s].astype(np.float32)
            carve = self._numeral_carve(xs - pad, ys - pad, r, numerals[i],
                                        self._rng.random() * math.tau)
            self._bake_carve(px, py, carve)
            wx, wz = self._px_to_world(px, py)
            self.glyphs.append({'gid': i, 'wx': wx, 'wz': wz, 'px': px, 'py': py,
                                'carve': carve, 'glint': 0.0})
        self._glint_gold = np.array([255, 214, 120], np.float32)

        self._island = self._build_island_patch(
            seed, edge_col=np.array([52, 46, 40], np.float32),
            core_col=np.array([108, 96, 80], np.float32))

        self.flies = []  # dust motes (streamed under the same state key)

        # crack mouths: fixed spots in the floor the scarabs pour from and
        # drain into (repeat visitors learn the holes)
        pts2 = self._interior_pts(0.30)
        self.mouths = []
        for _ in range(200):
            if len(self.mouths) >= 6:
                break
            py, px = pts2[self._rng.randrange(len(pts2))]
            px, py = float(px), float(py)
            if math.hypot(px - self.mast[0], py - self.mast[1]) < self.mast[2] + 0.45 * self.ppm:
                continue
            if any(math.hypot(px - m['px'], py - m['py']) < 0.9 * self.ppm
                   for m in self.mouths):
                continue
            wx, wz = self._px_to_world(px, py)
            self.mouths.append({'px': px, 'py': py, 'wx': wx, 'wz': wz})
        self._bake_holes()
        self._scarab_sprites = [
            self._build_scarab_sprite(k * math.tau / SCARAB_ROT_STEPS)
            for k in range(SCARAB_ROT_STEPS)]
        self._swarm = {'mode': 'idle', 'next': self._rng.uniform(*SCARAB_FIRST_S),
                       'scarabs': [], 'n': 0, 'spawned': 0, 't0': 0.0,
                       'mouth': None, 'exit': None, 'wp': 'exit', 'orbit_t': 0.0}

        # the fallen torch: dropped near the deck edge, flame licking toward
        # the interior. Handle/head/scorch bake into the base; the flame and
        # its guttering light pool are live.
        pts3 = self._interior_pts(0.30)
        best, best_d = None, -1.0
        alt, alt_d = None, -1.0  # fallback: altar rule only
        for _ in range(150):
            py, px = pts3[self._rng.randrange(len(pts3))]
            px, py = float(px), float(py)
            wx, wz = self._px_to_world(px, py)
            d = math.hypot(wx - self._cx, wz - self._cz)
            if d < 0.8:  # never against the altar
                continue
            if d > alt_d:
                alt, alt_d = (px, py, wx, wz), d
            if any(math.hypot(px - m['px'], py - m['py']) < 0.35 * self.ppm
                   for m in self.mouths):
                continue
            if any(math.hypot(px - g['px'], py - g['py']) < 0.35 * self.ppm
                   for g in self.glyphs):
                continue
            if d > best_d:  # farthest from center wins = off to the side
                best, best_d = (px, py, wx, wz), d
        px, py, wx, wz = best or alt
        ang = math.atan2(self.mast[1] - py, self.mast[0] - px) \
            + self._rng.uniform(-0.7, 0.7)  # flame roughly toward the interior
        self._torch = {'px': px, 'py': py, 'wx': wx, 'wz': wz, 'ang': ang,
                       'len': TORCH_FLAME_M * self.ppm, 'sway': 0.0,
                       'glow': 1.0, 'sput_next': self._rng.uniform(*TORCH_SPUTTER_S),
                       'sput_t': -1.0}
        self._bake_torch()

    def _flag_base(self, seed):
        """Dark weathered flagstones, brick-offset with wandering joints,
        moss in the gaps and creeping onto the stone, long cracks."""
        rng = np.random.default_rng(seed)
        gh, gw, ppm = self.gh, self.gw, self.ppm
        ys, xs = np.mgrid[0:gh, 0:gw].astype(np.float32)
        cs = 0.55 * ppm
        jx = xs + (_static_noise(rng, gh, gw, 9) - 0.5) * 0.17 * ppm
        jy = ys + (_static_noise(rng, gh, gw, 9) - 0.5) * 0.17 * ppm
        row = np.floor(jy / cs)
        jx = jx + (row % 2) * cs * 0.5
        colidx = np.floor(jx / cs)
        fx, fy = jx / cs - colidx, jy / cs - row
        edge = np.minimum(np.minimum(fx, 1 - fx), np.minimum(fy, 1 - fy))
        cellv = np.sin(colidx * 73.13 + row * 41.7) * 0.5 + 0.5
        stone = 60 + 30 * cellv
        mottle = 0.85 + 0.30 * _static_noise(rng, gh, gw, 40)
        base = (stone * mottle)[..., None] * np.array([1.08, 1.0, 0.82], np.float32)
        jm = np.clip(1 - edge * cs / (0.032 * ppm), 0, 1)[..., None]
        mossn = np.clip(_static_noise(rng, gh, gw, 7) * 1.9 - 0.35, 0, 1)
        joint = np.where(mossn[..., None] > 0.35,
                         np.array([40, 66, 30], np.float32),
                         np.array([30, 30, 26], np.float32))
        base = base * (1 - jm) + joint * jm
        creep = (np.clip(1 - edge * cs / (0.17 * ppm), 0, 1) * mossn)[..., None]
        base = base * (1 - creep * np.array([0.45, 0.06, 0.50], np.float32))
        crack = np.clip(1 - np.abs(_static_noise(rng, gh, gw, 6) - 0.5) / 0.03, 0, 1)
        return (base * (1 - 0.4 * crack)[..., None]).astype(np.float32)

    def _bake_carve(self, px, py, carve):
        """Chisel a glyph into the base texture (darkened groove + lip)."""
        s = carve.shape[0]
        x0 = int(round(px)) - s // 2
        y0 = int(round(py)) - s // 2
        sx0, sy0 = max(0, -x0), max(0, -y0)
        x0c, y0c = max(0, x0), max(0, y0)
        x1 = min(self.gw, x0 + s)
        y1 = min(self.gh, y0 + s)
        if x1 <= x0c or y1 <= y0c:
            return
        c = carve[sy0:sy0 + y1 - y0c, sx0:sx0 + x1 - x0c]
        lip = np.clip(np.roll(carve, 2, axis=0) - carve, 0.0, 1.0)[
            sy0:sy0 + y1 - y0c, sx0:sx0 + x1 - x0c]
        region = self._base[y0c:y1, x0c:x1]
        region *= 1.0 - c[..., None] * (1.0 - _CARVE_DARK)
        region += lip[..., None] * 16.0

    def _bake_torch(self):
        """Draw the dropped BONE torch into the base texture: a pale femur —
        twin condyle knobs at the free end, shaft with a dome highlight —
        with a mummy-cloth wrap at the burning end (diagonal bandage bands,
        charring toward the flame), a contact shadow so it lifts off the
        floor, and a soot scorch on the stone. The flame itself is live."""
        t = self._torch
        ca, sa = math.cos(t['ang']), math.sin(t['ang'])
        bl = TORCH_BONE_M * self.ppm
        wl = TORCH_WRAP_M * self.ppm
        pad = int(bl + wl) + 6
        x0 = max(0, int(t['px']) - pad)
        x1 = min(self.gw, int(t['px']) + pad + 1)
        y0 = max(0, int(t['py']) - pad)
        y1 = min(self.gh, int(t['py']) + pad + 1)
        ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        u = (xs - t['px']) * ca + (ys - t['py']) * sa   # +u = flame direction
        v = -(xs - t['px']) * sa + (ys - t['py']) * ca
        region = self._base[y0:y1, x0:x1]

        # scorch first, so everything lies on top of it
        d = np.hypot(u - 0.06 * self.ppm, v)
        region *= (1.0 - 0.55 * np.exp(-(d / (0.13 * self.ppm)) ** 2))[..., None]

        # silhouette pieces (alphas), assembled then shaded
        wsh = max(1.8, 0.032 * self.ppm)               # shaft half-width
        a_shaft = (np.clip((wsh - np.abs(v)) / 1.1, 0.0, 1.0)
                   * np.clip((-u - wl * 0.35) / 1.5, 0.0, 1.0)
                   * np.clip((u + bl - 0.05 * self.ppm) / 1.5, 0.0, 1.0))
        rk = max(2.2, 0.048 * self.ppm)                # condyle knobs
        a_knob = np.zeros_like(a_shaft)
        for sv in (-1, 1):
            dk = np.hypot(u + bl - 0.01 * self.ppm, v - sv * 0.034 * self.ppm)
            a_knob = np.maximum(a_knob, np.clip((rk - dk) / 1.1, 0.0, 1.0))
        a_bone = np.maximum(a_shaft, a_knob)
        wwr = max(2.4, 0.058 * self.ppm)               # cloth wrap half-width
        a_wrap = (np.clip((wwr - np.abs(v)) / 1.1, 0.0, 1.0)
                  * np.clip((u + wl * 0.45) / 1.2, 0.0, 1.0)
                  * np.clip((wl * 0.55 - u) / 1.2, 0.0, 1.0))

        # contact shadow: the silhouette shifted a touch, darkening the stone
        sil = np.maximum(a_bone, a_wrap)
        sh = np.roll(np.roll(sil, 2, axis=0), 1, axis=1)
        region *= (1.0 - 0.40 * sh)[..., None]

        # bone: dome highlight across the shaft, worn shading at the edges
        dome = np.clip(1.0 - np.abs(v) / (wsh * 1.4), 0.0, 1.0) ** 0.7
        col_bone = _BONE_DARK + (_BONE - _BONE_DARK) * dome[..., None]
        col_bone = col_bone * (1.0 + 0.06 * np.sin(u * 1.3))[..., None]
        region[:] = region * (1 - a_bone[..., None]) + col_bone * a_bone[..., None]

        # cloth: diagonal bandage bands, charring toward the flame end
        band = 1.0 + 0.24 * np.sin((u - v * 0.9) * (4.2 / max(1.0, 0.02 * self.ppm)))
        char = np.clip((u + wl * 0.1) / (wl * 0.6), 0.0, 1.0) ** 1.5
        col_wrap = (_CLOTH * band[..., None]
                    + char[..., None] * (_CLOTH_CHAR - _CLOTH * band[..., None]))
        region[:] = region * (1 - a_wrap[..., None]) + col_wrap * a_wrap[..., None]

    def _bake_holes(self):
        """The pits the scarabs use, chipped into the floor: near-black
        irregular holes with a bright fractured rim — always visible, so
        repeat visitors can watch the right spots."""
        for m in self.mouths:
            r = self._rng.uniform(*HOLE_R_M) * self.ppm
            wob = [self._rng.uniform(-1, 1) for _ in range(12)]
            pad = int(r * 1.8) + 3
            x0 = max(0, int(m['px']) - pad)
            x1 = min(self.gw, int(m['px']) + pad + 1)
            y0 = max(0, int(m['py']) - pad)
            y1 = min(self.gh, int(m['py']) + pad + 1)
            ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)
            dx, dy = xs - m['px'], ys - m['py']
            d = np.hypot(dx, dy)
            th = np.arctan2(dy, dx)
            idx = (th + math.pi) / math.tau * 12
            i0 = np.floor(idx).astype(np.int32) % 12
            f = (idx - np.floor(idx)).astype(np.float32)
            wt = np.asarray(wob, np.float32)
            edge = r * (1 + 0.28 * (wt[i0] * (1 - f) + wt[(i0 + 1) % 12] * f))
            hole = np.clip((edge - d) / 1.1, 0.0, 1.0)[..., None]
            rim = np.clip((edge + 1.8 - d) / 1.1, 0.0, 1.0)[..., None] - hole
            region = self._base[y0:y1, x0:x1]
            region[:] = region * (1 + 0.30 * rim)      # chipped bright lip
            region[:] = (region * (1 - hole)
                         + np.array([9, 8, 7], np.float32) * hole)

    def _build_scarab_sprite(self, ang):
        """One scarab seen from above, pointing along `ang`: a tiny dark
        oval — split elytra line down the back, bronze-green iridescent
        sheen toward the head. Precomputed like the monster/rot patches."""
        L = SCARAB_L_M * self.ppm / 2
        W = L * 0.62
        pad = int(math.ceil(L)) + 2
        s = 2 * pad + 1
        ys, xs = np.mgrid[0:s, 0:s].astype(np.float32)
        dx, dy = xs - pad, ys - pad
        ca, sa = math.cos(ang), math.sin(ang)
        u = dx * ca + dy * sa
        v = -dx * sa + dy * ca
        ell = (u / L) ** 2 + (v / max(W, 1e-3)) ** 2
        alpha = np.clip((1.0 - ell) * 2.2, 0.0, 1.0)[..., None]
        shade = 0.75 + 0.45 * np.clip(1.0 - ell, 0.0, 1.0)
        col = _SCARAB_BODY * shade[..., None]
        seam = np.clip(1.0 - np.abs(v) / 0.5, 0.0, 1.0) * (u < 0.2 * L)
        col = col * (1.0 - 0.35 * seam[..., None])
        sheen = np.exp(-(((u - 0.35 * L) ** 2 + v * v) / max(0.5 * W, 1e-3) ** 2))
        col = col + sheen[..., None] * (_SCARAB_SHEEN - col) * 0.55
        return col.astype(np.float32), alpha.astype(np.float32)

    # ---- simulation ----
    def _step_theme(self, dt):
        self._step_torch(dt)
        self._step_motes(dt)
        self._step_scarabs(dt)
        self._step_glints(dt)

    def _step_torch(self, dt):
        """Flame flicker (two-sine + jitter), lateral sway, and the
        occasional dramatic sputter: gutter down, flare, recover."""
        t = self._torch
        env = 1.0
        if t['sput_t'] >= 0:
            ph = t['sput_t'] = t['sput_t'] + dt
            if ph < 0.5:
                env = 1.0 - 1.3 * ph            # gutter down to ~0.35
            elif ph < 0.8:
                env = 0.35 + (ph - 0.5) * 3.0   # flare up through 1.25
            elif ph < 1.3:
                env = 1.25 - (ph - 0.8) * 0.5   # settle back
            else:
                t['sput_t'] = -1.0
                t['sput_next'] = self._rng.uniform(*TORCH_SPUTTER_S)
        elif self.fade > 0.5:
            t['sput_next'] -= dt
            if t['sput_next'] <= 0:
                t['sput_t'] = 0.0
                self._emit({'e': 'torch_sputter'})
        flick = (1.0 + 0.16 * math.sin(self.t * 9.1)
                 + 0.09 * math.sin(self.t * 15.7)
                 + self._rng.uniform(-0.05, 0.05))
        t['len'] = TORCH_FLAME_M * self.ppm * flick * env
        t['sway'] = (0.35 * math.sin(self.t * 7.3)
                     + 0.22 * math.sin(self.t * 12.1)) * 0.05 * self.ppm
        t['glow'] = max(0.15, flick * env)

    def _step_scarabs(self, dt):
        sw = self._swarm
        if sw['mode'] == 'idle':
            if self.fade > 0.5 and len(self.mouths) >= 2:
                sw['next'] -= dt
                if sw['next'] <= 0:
                    sw['mouth'] = self._rng.choice(self.mouths)
                    sw['exit'] = self._rng.choice(
                        [m for m in self.mouths if m is not sw['mouth']])
                    sw['n'] = self._rng.randint(*SCARAB_N)
                    sw['spawned'] = 0
                    sw['scarabs'] = []
                    sw['t0'] = self.t
                    sw['mode'] = 'erupt'
                    sw['wp'] = 'exit'
                    self._emit({'e': 'scarab_erupt',
                                'x': round(sw['mouth']['px'], 1),
                                'y': round(sw['mouth']['py'], 1)})
            return
        if self.fade <= 0:  # show died mid-swarm: vanish quietly
            sw['mode'] = 'idle'
            sw['scarabs'] = []
            sw['next'] = self._rng.uniform(*SCARAB_GAP_S)
            return

        if sw['mode'] == 'erupt':
            want = min(sw['n'], int(sw['n'] * (self.t - sw['t0']) / SCARAB_ERUPT_S) + 1)
            mo = sw['mouth']
            while sw['spawned'] < want:
                a = self._rng.random() * math.tau
                r = self._rng.uniform(0.02, 0.10)
                sw['scarabs'].append({
                    'x': mo['wx'] + math.cos(a) * r, 'z': mo['wz'] + math.sin(a) * r,
                    'ang': a, 'spd': self._rng.uniform(*SCARAB_SPEED),
                    'ph': self._rng.uniform(0.05, 0.2), 'moving': False,
                    'oa': self._rng.random() * math.tau,
                    'orr': self._rng.uniform(0.6, 1.3)})
                sw['spawned'] += 1
            if sw['spawned'] >= sw['n']:
                fresh = self._fresh_tracks()
                if fresh:
                    sw['wp'] = 'walker'
                    sw['orbit_t'] = self._rng.uniform(*SCARAB_ORBIT_S)
                sw['mode'] = 'travel'
            return

        # travel: every scarab dashes-and-pauses toward its own slot in the
        # formation; the formation centers on the walker (circling) or the
        # exit crack. The Mummy rules: swarm the feet, never touch.
        fresh = self._fresh_tracks()
        if sw['wp'] == 'walker':
            sw['orbit_t'] -= dt
            if not fresh or sw['orbit_t'] <= 0:
                sw['wp'] = 'exit'
        force_drain = self.t - sw['t0'] > SCARAB_MAX_S
        ex = sw['exit']
        alive = []
        for f in sw['scarabs']:
            if sw['wp'] == 'walker' and fresh:
                w = fresh[0]
                oa = f['oa'] + self.t * 2.4
                tx = w.x + math.cos(oa) * SCARAB_ORBIT_R_M
                tz = w.z + math.sin(oa) * SCARAB_ORBIT_R_M
            else:
                # loose mass in transit, funneling tight as it reaches the
                # crack (offsets shrink with distance-to-exit → they spiral in)
                dex = math.hypot(ex['wx'] - f['x'], ex['wz'] - f['z'])
                spread = 0.22 * f['orr'] * min(1.0, dex / 0.5)
                tx = ex['wx'] + math.cos(f['oa']) * spread
                tz = ex['wz'] + math.sin(f['oa']) * spread
            dxx, dzz = tx - f['x'], tz - f['z']
            d = math.hypot(dxx, dzz)
            if sw['wp'] == 'exit' and (d < 0.10 or force_drain):
                continue  # gone between the stones
            f['ph'] -= dt
            if f['ph'] <= 0:  # flip between a dash and a twitchy pause
                f['moving'] = not f['moving']
                f['ph'] = (self._rng.uniform(0.15, 0.40) if f['moving']
                           else self._rng.uniform(0.04, 0.18))
            bearing = math.atan2(dzz, dxx)
            f['ang'] += _angdiff(bearing, f['ang']) * min(1.0, 9.0 * dt)
            if f['moving']:
                f['ang'] += self._rng.uniform(-1.0, 1.0) * 2.2 * dt
                step = f['spd'] * dt
                f['x'] += math.cos(f['ang']) * min(step, d)
                f['z'] += math.sin(f['ang']) * min(step, d)
                if not self._on_deck(f['x'], f['z'], thresh=0.3):
                    f['x'] -= math.cos(f['ang']) * min(step, d)
                    f['z'] -= math.sin(f['ang']) * min(step, d)
                    f['ang'] = math.atan2(ex['wz'] - f['z'], ex['wx'] - f['x'])
            alive.append(f)
        sw['scarabs'] = alive
        if not alive:
            sw['mode'] = 'idle'
            sw['next'] = self._rng.uniform(*SCARAB_GAP_S)
            self._emit({'e': 'scarab_drain',
                        'x': round(ex['px'], 1), 'y': round(ex['py'], 1)})

    def _step_motes(self, dt):
        if (self.fade > 0 and len(self.flies) < MOTE_N
                and self._rng.random() < 0.5 * dt * self.fade):
            py, px = self._mask_pts[self._rng.randrange(len(self._mask_pts))]
            a = self._rng.random() * math.tau
            sp = self._rng.uniform(0.015, 0.04) * self.ppm  # slow drift
            self.flies.append({'x': float(px), 'y': float(py),
                               'vx': math.cos(a) * sp, 'vy': math.sin(a) * sp,
                               't0': self.t, 'life': self._rng.uniform(12.0, 28.0),
                               'on': False, 'sw': self._rng.uniform(0.8, 2.5)})
        alive = []
        for f in self.flies:
            if self.t - f['t0'] >= f['life']:
                continue
            turn = self._rng.uniform(-1.0, 1.0) * 1.1 * dt
            ca, sa = math.cos(turn), math.sin(turn)
            f['vx'], f['vy'] = f['vx'] * ca - f['vy'] * sa, f['vx'] * sa + f['vy'] * ca
            f['x'] += f['vx'] * dt
            f['y'] += f['vy'] * dt
            xi, yi = int(f['x']), int(f['y'])
            if not (0 <= xi < self.gw and 0 <= yi < self.gh) or self.mask[yi, xi] < 0.5:
                sp = math.hypot(f['vx'], f['vy'])
                d = math.hypot(self.mast[0] - f['x'], self.mast[1] - f['y']) or 1.0
                f['vx'] = (self.mast[0] - f['x']) / d * sp
                f['vy'] = (self.mast[1] - f['y']) / d * sp
            f['sw'] -= dt
            if f['sw'] <= 0:
                f['on'] = not f['on']
                f['sw'] = (self._rng.uniform(1.2, 2.8) if f['on']
                           else self._rng.uniform(1.5, 4.0))
            alive.append(f)
        self.flies = alive

    def _step_glints(self, dt):
        k = min(1.0, dt * 6.0)
        fresh = self._fresh_tracks()
        for g in self.glyphs:
            if not fresh:
                g['glint'] += (0.0 - g['glint']) * k
                continue
            dmin = min(math.hypot(t.x - g['wx'], t.z - g['wz']) for t in fresh)
            target = np.clip(1.0 - (dmin - 0.35) / GLINT_R_M, 0.0, 1.0) * 0.7
            g['glint'] += (float(target) - g['glint']) * k

    # ---- output ----
    def _field_blobs(self, h):
        # torchlight breathes over the whole floor
        h += np.float32(0.035 * (math.sin(self.t * 6.3)
                                 + 0.6 * math.sin(self.t * 9.7)))
        for t in self.tracks.values():
            if self.t - t.last < TRACK_STALE_S:
                px, py = self.to_px(t.x, t.z)
                self._add_blob(h, px, py, SUN_R_M * self.ppm, SUN_AMOUNT)
        for f in self.flies:
            if f['on']:
                self._add_blob(h, f['x'], f['y'], 2.0, 0.35)
        sw = self._swarm
        if sw['scarabs']:
            # the swarm carries its own shadow — the light dims under the mass
            cx = sum(f['x'] for f in sw['scarabs']) / len(sw['scarabs'])
            cz = sum(f['z'] for f in sw['scarabs']) / len(sw['scarabs'])
            px, py = self.to_px(cx, cz)
            self._add_blob(h, px, py, 0.30 * self.ppm, -0.22)
        if sw['mode'] == 'erupt':
            self._add_blob(h, sw['mouth']['px'], sw['mouth']['py'],
                           0.12 * self.ppm, 0.30)  # dust catching the light
        # the fallen torch owns a guttering pool of light
        t = self._torch
        fx = t['px'] + math.cos(t['ang']) * t['len'] * 0.4
        fy = t['py'] + math.sin(t['ang']) * t['len'] * 0.4
        self._add_blob(h, fx, fy, TORCH_POOL_R_M * self.ppm, 0.34 * t['glow'])
        self._add_blob(h, fx, fy, 0.16 * self.ppm, 0.30 * t['glow'])

    def _draw(self, rgb):
        for g in self.glyphs:
            if g['glint'] > 0.02:  # the carve fills with gold on approach
                gold = np.broadcast_to(self._glint_gold,
                                       g['carve'].shape + (3,))
                self._composite_patch(rgb, g['px'], g['py'], gold,
                                      (g['carve'] * (g['glint'] * 0.85))[..., None])
        self._draw_island(rgb)
        for f in self._swarm['scarabs']:
            px, py = self.to_px(f['x'], f['z'])
            k = int(round(f['ang'] / (math.tau / SCARAB_ROT_STEPS))) % SCARAB_ROT_STEPS
            col, alpha = self._scarab_sprites[k]
            self._composite_patch(rgb, px, py, col, alpha)
        self._draw_flame(rgb)
        for f in self.flies:
            if f['on']:
                self._dot(rgb, f['x'], f['y'], 1.0, _FLY_CORE)

    def _draw_flame(self, rgb):
        """The live flame licking along the floor from the torch head: a
        sheared teardrop, three heat zones (outer orange → mid → white-hot
        core), rebuilt every frame — the region is tiny."""
        t = self._torch
        L = max(3.0, t['len'])
        ca, sa = math.cos(t['ang']), math.sin(t['ang'])
        cx = t['px'] + ca * L * 0.45
        cy = t['py'] + sa * L * 0.45
        pad = int(L * 0.75) + 3
        x0, x1 = max(0, int(cx) - pad), min(self.gw, int(cx) + pad + 1)
        y0, y1 = max(0, int(cy) - pad), min(self.gh, int(cy) + pad + 1)
        if x1 <= x0 or y1 <= y0:
            return
        ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        u = (xs - t['px']) * ca + (ys - t['py']) * sa
        v = -(xs - t['px']) * sa + (ys - t['py']) * ca
        s = np.clip(u / L, 0.0, 1.0)
        v = v - t['sway'] * s * s        # tip sways harder than the root
        w = 0.055 * self.ppm * (1.0 - s) ** 0.65 + 0.4
        a = (np.clip((w - np.abs(v)) / 1.1, 0.0, 1.0)
             * np.clip(u / 1.5 + 1.0, 0.0, 1.0)
             * np.clip((L - u) / 1.5, 0.0, 1.0))
        if a.max() <= 0:
            return
        heat = np.clip(s + np.abs(v) / (w + 0.5) * 0.35, 0.0, 1.0)
        col = np.where(heat[..., None] < 0.35, _FLAME_CORE,
                       np.where(heat[..., None] < 0.7, _FLAME_MID, _FLAME_OUT))
        region = rgb[y0:y1, x0:x1]
        aa = (a * 0.95)[..., None]
        region[:] = region * (1 - aa) + col * aa

    _dot = JungleShow._dot  # same tiny stamp helper

    def hello_patches(self):
        """Temple artwork for the sim page: the floor base (multiplied by
        the light stream client-side), the altar, and per-glyph gold carve
        sprites (glow: the page draws them at the streamed glint alpha)."""
        icol, ialpha = self._island
        glyphs = []
        for g in self.glyphs:
            gold = np.empty(g['carve'].shape + (3,), np.float32)
            gold[:] = (255, 214, 120)
            glyphs.append({'id': g['gid'], 'x': round(g['px'], 1),
                           'y': round(g['py'], 1), 'glow': 1,
                           **self._pack_patch(gold, g['carve'][..., None] * 0.85)})
        ones = np.ones(self._base.shape[:2] + (1,), np.float32)
        return {'base': self._pack_patch(self._base, ones),
                'island': {'x': round(self.mast[0], 1), 'y': round(self.mast[1], 1),
                           **self._pack_patch(icol, ialpha)},
                'glyphs': glyphs}

    def _state_extra(self):
        return {
            'flies': [{'x': round(f['x'], 1), 'y': round(f['y'], 1)}
                      for f in self.flies if f['on']],
            'glyphs': [{'id': g['gid'], 'glint': round(g['glint'], 2)}
                       for g in self.glyphs],
            'scarabs': [[round(px, 1), round(py, 1), round(f['ang'], 2)]
                        for px, py, f in
                        ((*self.to_px(f['x'], f['z']), f)
                         for f in self._swarm['scarabs'])],
            'torch': {'x': round(self._torch['px'], 1),
                      'y': round(self._torch['py'], 1),
                      'ang': round(self._torch['ang'], 3),
                      'len': round(self._torch['len'], 1),
                      'sway': round(self._torch['sway'], 2),
                      'glow': round(self._torch['glow'], 2)},
        }


THEMES = {'lava': LavaShow, 'jungle': JungleShow, 'temple': TempleShow}
