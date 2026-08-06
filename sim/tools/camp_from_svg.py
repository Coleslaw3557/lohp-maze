#!/usr/bin/env python3
"""Bake LotHP-26-v3.svg (Jen's camp placement drawing) into sim/web/camp_layout_data.js.

The drawing is 1 ft = 1 mm at 72 dpi (2.83465 SVG units per foot — the labeled
175' B-street edge measures 496.21 units). The plan is anchored onto the sim
world through the maze itself: the drawing's maze hex centroid + wing axis are
mapped onto maze_layout.json's hex_center with the maze bar along +x and the
street/plaza toward +z. Everything else (lot line, shades, trailer, carports,
cars, tank, generator, shower, bike racks, fuel circles) is emitted in WORLD
METERS so camp_layout.js places it with zero runtime math.

Re-run after any LotHP-26-v*.svg revision:  python3 sim/tools/camp_from_svg.py
"""
import json
import math
import re
import sys
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[2]
SVG = ROOT / 'LotHP-26-v3.svg'
LAYOUT = ROOT / 'sim' / 'maze_layout.json'
OUT = ROOT / 'sim' / 'web' / 'camp_layout_data.js'

UNITS_PER_FT = 72 / 25.4  # 2.83465: the drawing is 1 ft = 1 mm at 72 dpi
FT = 0.3048


# ------------------------------------------------------------- affine helpers
def mat_identity():
    return (1, 0, 0, 1, 0, 0)  # a b c d e f  (SVG matrix column order)


def mat_mul(m, n):
    a, b, c, d, e, f = m
    a2, b2, c2, d2, e2, f2 = n
    return (a * a2 + c * b2, b * a2 + d * b2,
            a * c2 + c * d2, b * c2 + d * d2,
            a * e2 + c * f2 + e, b * e2 + d * f2 + f)


def mat_apply(m, pt):
    a, b, c, d, e, f = m
    x, y = pt
    return (a * x + c * y + e, b * x + d * y + f)


def parse_transform(s):
    """SVG transform list -> single matrix (applied left to right)."""
    m = mat_identity()
    for fn, args in re.findall(r'(\w+)\s*\(([^)]*)\)', s or ''):
        v = [float(t) for t in re.split(r'[\s,]+', args.strip()) if t]
        if fn == 'translate':
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif fn == 'rotate':
            r = math.radians(v[0])
            t = (math.cos(r), math.sin(r), -math.sin(r), math.cos(r), 0, 0)
            if len(v) == 3:  # rotate about a point
                t = mat_mul(mat_mul((1, 0, 0, 1, v[1], v[2]), t), (1, 0, 0, 1, -v[1], -v[2]))
        elif fn == 'matrix':
            t = tuple(v)
        elif fn == 'scale':
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        else:
            raise ValueError(f'unhandled transform {fn}')
        m = mat_mul(m, t)
    return m


def rect_corners(el):
    x, y = float(el.get('x')), float(el.get('y'))
    w, h = float(el.get('width')), float(el.get('height'))
    m = parse_transform(el.get('transform'))
    return [mat_apply(m, p) for p in ((x, y), (x + w, y), (x + w, y + h), (x, y + h))]


def arc_points(p0, r, large, sweep, p1, n=22):
    """Sample a circular SVG arc (rx==ry, no x-rotation) into n points after p0."""
    x0, y0 = p0
    x1, y1 = p1
    # SVG F.6.5 endpoint -> center parameterization, simplified for circles
    dx, dy = (x0 - x1) / 2, (y0 - y1) / 2
    lam = (dx * dx + dy * dy) / (r * r)
    if lam > 1:
        r *= math.sqrt(lam)
    sq = math.sqrt(max(0, (r * r - dx * dx - dy * dy) / (dx * dx + dy * dy)))
    if large == sweep:
        sq = -sq
    cxp, cyp = sq * dy, -sq * dx
    cx, cy = cxp + (x0 + x1) / 2, cyp + (y0 + y1) / 2
    a0 = math.atan2(y0 - cy, x0 - cx)
    a1 = math.atan2(y1 - cy, x1 - cx)
    da = a1 - a0
    if not sweep and da > 0:
        da -= 2 * math.pi
    if sweep and da < 0:
        da += 2 * math.pi
    return [(cx + r * math.cos(a0 + da * i / n), cy + r * math.sin(a0 + da * i / n))
            for i in range(1, n + 1)]


def arc_center(p0, r, large, sweep, p1):
    """Circle center of an SVG arc (rx==ry, no rotation), F.6.5 simplified."""
    x0, y0 = p0
    x1, y1 = p1
    dx, dy = (x0 - x1) / 2, (y0 - y1) / 2
    lam = (dx * dx + dy * dy) / (r * r)
    if lam > 1:
        r *= math.sqrt(lam)
    sq = math.sqrt(max(0, (r * r - dx * dx - dy * dy) / (dx * dx + dy * dy)))
    if large == sweep:
        sq = -sq
    return (sq * dy + (x0 + x1) / 2, -sq * dx + (y0 + y1) / 2)


def lot_polygon(el):
    """The cls-13 lot path: M v h v a h l Z with its own translate."""
    m = parse_transform(el.get('transform'))
    d = el.get('d')
    tok = re.findall(r'([MvhalZ])|(-?\d*\.?\d+)', d)
    nums, ops = [], []
    for op, num in tok:
        if op:
            ops.append((op, []))
        else:
            ops[-1][1].append(float(num))
    pts, cur = [], (0, 0)
    for op, v in ops:
        if op == 'M':
            cur = (v[0], v[1])
            pts.append(cur)
        elif op == 'v':
            for dy in v:
                cur = (cur[0], cur[1] + dy)
                pts.append(cur)
        elif op == 'h':
            for dx in v:
                cur = (cur[0] + dx, cur[1])
                pts.append(cur)
        elif op == 'l':
            for i in range(0, len(v), 2):
                cur = (cur[0] + v[i], cur[1] + v[i + 1])
                pts.append(cur)
        elif op == 'a':
            r, _ry, _rot, large, sweep, ex, ey = v
            end = (cur[0] + ex, cur[1] + ey)
            pts.extend(arc_points(cur, r, int(large), int(sweep), end))
            lot_polygon.arc = dict(  # the plaza-frontage arc: its circle IS the plaza
                center=mat_apply(m, arc_center(cur, r, int(large), int(sweep), end)),
                r=r)
            cur = end
        elif op == 'Z':
            pass
    return [mat_apply(m, p) for p in pts]


# ------------------------------------------------------------------ svg parse
def load_shapes():
    svg = ElementTree.parse(SVG).getroot()
    ns = {'s': 'http://www.w3.org/2000/svg'}
    shapes = {'rects': [], 'circles': [], 'polygons': [], 'lot': None}
    for el in svg.iter():
        tag = el.tag.split('}')[-1]
        cls = el.get('class', '')
        if tag == 'path' and cls == 'cls-13':
            shapes['lot'] = lot_polygon(el)
        elif tag == 'rect':
            w = float(el.get('width'))
            if w < 3:  # bike-rack slat decoration
                continue
            shapes['rects'].append((cls, rect_corners(el)))
        elif tag == 'circle':
            m = parse_transform(el.get('transform'))
            shapes['circles'].append((cls, mat_apply(m, (float(el.get('cx')), float(el.get('cy')))),
                                      float(el.get('r'))))
        elif tag == 'polygon':
            v = [float(t) for t in re.split(r'[\s,]+', el.get('points').strip())]
            shapes['polygons'].append((cls, [(v[i], v[i + 1]) for i in range(0, len(v), 2)]))
    return shapes


# --------------------------------------------------------------- world mapping
def build_frame(shapes):
    """Anchor: drawing maze hex centroid -> hex_center world, wing axis -> +x."""
    hexes = [p for c, p in shapes['polygons'] if c == 'cls-32' and len(p) >= 6]
    if len(hexes) != 1:
        sys.exit(f'expected 1 maze hex polygon, found {len(hexes)}')
    hx = sum(p[0] for p in hexes[0]) / len(hexes[0])
    hy = sum(p[1] for p in hexes[0]) / len(hexes[0])
    # maze axis from the two cls-32 wing rects: their long edges
    wings = [c for cl, c in shapes['rects'] if cl == 'cls-32']
    if len(wings) != 2:
        sys.exit(f'expected 2 maze wing rects, found {len(wings)}')
    axes = []
    for c in wings:
        v = (c[1][0] - c[0][0], c[1][1] - c[0][1])
        n = math.hypot(*v)
        v = (v[0] / n, v[1] / n)
        if v[0] < 0:
            v = (-v[0], -v[1])
        axes.append(v)
    ax = ((axes[0][0] + axes[1][0]) / 2, (axes[0][1] + axes[1][1]) / 2)
    n = math.hypot(*ax)
    ax = (ax[0] / n, ax[1] / n)              # svg maze axis, pointing screen-right (east wing)
    perp = (ax[1], -ax[0])                    # rotate -90 in svg coords: toward the plaza
    L = json.loads(LAYOUT.read_text())
    hc = L['hex_center']
    world = (float(hc['cx']), float(hc['cz']))
    s = FT / UNITS_PER_FT                     # metres per svg unit

    def to_world(p):
        dx, dy = p[0] - hx, p[1] - hy
        return (round(world[0] + s * (dx * ax[0] + dy * ax[1]), 3),
                round(world[1] + s * (dx * perp[0] + dy * perp[1]), 3))

    # a plan-frame-aligned svg rect keeps rot 0 in world only if drawn along the
    # maze axis; an unrotated svg rect lands rotated by the axis angle
    return to_world, ax, perp, (hx, hy)


def obb(corners, to_world, ax):
    """Rect corners (svg) -> world {cx, cz, w, d, rot} with rot in radians.
    w runs along the rect's first edge, d along the second."""
    (x0, y0), (x1, y1), (x2, y2), _ = corners
    cxs = sum(c[0] for c in corners) / 4
    cys = sum(c[1] for c in corners) / 4
    w = math.hypot(x1 - x0, y1 - y0) / UNITS_PER_FT * FT
    d = math.hypot(x2 - x1, y2 - y1) / UNITS_PER_FT * FT
    e = ((x1 - x0), (y1 - y0))
    n = math.hypot(*e)
    e = (e[0] / n, e[1] / n)
    # angle of the rect's w-edge relative to the maze axis, in world Y-rotation
    # terms: world x' = cos, z' = -sin  ->  rot = atan2(-(e . perp), e . ax)
    perp = (ax[1], -ax[0])
    rot = math.atan2(-(e[0] * perp[0] + e[1] * perp[1]), e[0] * ax[0] + e[1] * ax[1])
    # normalize so local +z faces the street/plaza side — asymmetric renders
    # (communal doors, trailer tongue) rely on that meaning, mirror or not
    if math.cos(rot) < 0:
        rot = math.atan2(-math.sin(rot), -math.cos(rot))
    cx, cz = to_world((cxs, cys))
    return {'cx': cx, 'cz': cz, 'w': round(w, 3), 'd': round(d, 3), 'rot': round(rot, 5)}


def main():
    shapes = load_shapes()
    to_world, ax, perp, hex_svg = build_frame(shapes)

    # Tim 2026-08-06: the drawing is MIRRORED vs reality — flip the plot and
    # contents left/right around the maze (the maze itself stays put): reflect
    # every shape across the maze's cross line through the hex center. The
    # maze axis is reflection-stable, so the anchor frame is unchanged.
    hx, hy = hex_svg

    def reflect(p):
        a = (p[0] - hx) * ax[0] + (p[1] - hy) * ax[1]
        return (p[0] - 2 * a * ax[0], p[1] - 2 * a * ax[1])

    shapes['lot'] = [reflect(p) for p in shapes['lot']]
    lot_polygon.arc['center'] = reflect(lot_polygon.arc['center'])
    shapes['rects'] = [(c, [reflect(p) for p in pts]) for c, pts in shapes['rects']]
    shapes['circles'] = [(c, reflect(p), r) for c, p, r in shapes['circles']]

    # Tim 2026-08-06: re-seat the plan around the REAL maze. The drawn maze
    # bar is shorter than the sim's and offset within it, which (post-flip)
    # left the sim maze's west end poking past the lot line. Slide the plan
    # so the real bar centers in the drawn maze mark, and pull it 0.8 m
    # rearward so the maze sits closer to the 50' frontage (the drawing's
    # ~7 ft setback; much more and the entrance towers at z=5.6 would cross
    # the plaza rim off the property).
    rooms = json.loads(LAYOUT.read_text())['rooms']
    bar_cx = (min(r['x'] for r in rooms.values())
              + max(r['x'] + r['w'] for r in rooms.values())) / 2
    wing_x = [to_world(p)[0] for cls, corners in shapes['rects']
              if cls == 'cls-32' for p in corners]
    off = (round(bar_cx - (min(wing_x) + max(wing_x)) / 2, 3), -0.8)
    print(f'plan re-seat: {off[0]:+.2f} m along the bar, {off[1]:+.2f} m frontage-ward')
    anchored = to_world
    to_world = lambda p: tuple(round(c + o, 3) for c, o in zip(anchored(p), off))

    lot = [list(to_world(p)) for p in shapes['lot']]

    zones, items = [], []
    cars = []
    fives = []  # the two 5x5 cls-53 pads: shower box + generator
    for cls, corners in shapes['rects']:
        o = obb(corners, to_world, ax)
        wft, dft = o['w'] / FT, o['d'] / FT
        size = (round(wft), round(dft))
        if cls == 'cls-14':
            zones.append(dict(o, key='bds_strip', label="100' shared with Blazing Death Ship"))
        elif cls == 'cls-72':
            zones.append(dict(o, key='tiedown', label='maze tie-downs'))
        elif cls == 'cls-27':
            items.append(dict(o, kind='bike_rack', label='Bike Rack'))
        elif cls == 'cls-86':
            continue  # drawing legend box
        elif cls == 'cls-32':
            continue  # the maze itself: already in the sim
        elif cls == 'cls-53':
            if size == (5, 25) or size == (25, 5):
                items.append(dict(o, kind='evap', label='Shower & Evap'))
            else:
                fives.append(o)
        elif cls == 'cls-28':
            if size == (40, 40):
                zones.append(dict(o, key='communal', label='Camp Communal Space'))
            elif size == (55, 45) or size == (45, 55):
                zones.append(dict(o, key='brs_tents', label='Black Rock shade — tent campers'))
            elif size in ((12, 6), (6, 12)):
                cars.append(dict(o, kind='car'))
            elif size in ((8, 20), (20, 8)):
                items.append(dict(o, kind='container', label='OSS Container'))
            elif size in ((22, 32), (32, 22)):
                items.append(dict(o, kind='trailer_brs', label='Trailer + BRS'))
            else:
                sys.exit(f'unclassified cls-28 rect {size} at {o}')
        else:
            sys.exit(f'unclassified rect class {cls} {size}')
    if len(cars) != 6:
        sys.exit(f'expected 6 cars, found {len(cars)}')
    items.extend(cars)

    # generator vs shower box: the shower 5x5 touches the evap strip
    evap = next(i for i in items if i['kind'] == 'evap')
    fives.sort(key=lambda o: math.hypot(o['cx'] - evap['cx'], o['cz'] - evap['cz']))
    if len(fives) != 2:
        sys.exit(f'expected 2 five-foot pads, found {len(fives)}')
    items.append(dict(fives[0], kind='shower_box', label=None))
    items.append(dict(fives[1], kind='generator', label='Predator 5000'))

    for cls, c, r in shapes['circles']:
        cx, cz = to_world(c)
        rm = round(r / UNITS_PER_FT * FT, 3)
        if cls == 'cls-53':
            items.append({'kind': 'water', 'label': 'Water 500 gal', 'cx': cx, 'cz': cz, 'r': rm})
        elif cls == 'cls-63':
            items.append({'kind': 'fuel_pad', 'label': 'Fuel (shared w/ BDS)', 'cx': cx, 'cz': cz, 'r': rm})
        elif cls == 'cls-64':
            items.append({'kind': 'fuel_ring', 'label': None, 'cx': cx, 'cz': cz, 'r': rm})

    # frontage labels at the labeled edges' midpoints. The lot path runs
    # NE-corner -> SE -> SW -> NW(plaza) -> arc... -> tip -> close, so the
    # first four vertices bound the three straight labeled edges; the plaza
    # arc midpoint sits halfway along the sampled arc.
    v = shapes['lot']
    cen = to_world((sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v)))

    def mid(a, b):  # edge midpoint pushed 8 ft outside the lot line
        m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        d = math.hypot(m[0] - cen[0], m[1] - cen[1])
        return [round(m[0] + (m[0] - cen[0]) / d * 8 * FT, 3),
                round(m[1] + (m[1] - cen[1]) / d * 8 * FT, 3)]
    edges = {
        'neighbor': dict(pos=mid(*[to_world(p) for p in (v[0], v[1])]), label="150' border w/ neighbor"),
        'bds': dict(pos=mid(*[to_world(p) for p in (v[1], v[2])]), label="100' shared w/ Blazing Death Ship"),
        'b_street': dict(pos=mid(*[to_world(p) for p in (v[2], v[3])]), label="B Street — 175' frontage"),
        # west third of the arc, like the drawing — keeps it off the default
        # street-view center line
        'plaza': dict(pos=mid(to_world(v[3 + 5]), to_world(v[3 + 5])), label="4:30 & B Plaza @ 2:15 — 50' frontage"),
    }

    # ---- the plaza + the Man (Tim 2026-08-06: address is 4:30 & B plaza,
    # and WITHIN the plaza the camp sits at its 2:15 position). The frontage
    # arc's circle is the plaza rim. Plaza mini-clocks point 12:00 AT the Man
    # (radially inward) — that convention is pinned by geometry: with it, the
    # B-ring tangent it predicts runs parallel to the drawn B-street edge
    # (the skew printed below; the absolute-city-clock reading fails by ~55°).
    # So: Man direction = the camp's 2:15 bearing rotated back 67.5°.
    pc = to_world(lot_polygon.arc['center'])
    arc_mid = to_world(v[3 + 11])
    vc = (arc_mid[0] - pc[0], arc_mid[1] - pc[1])
    n = math.hypot(*vc)
    vc = (vc[0] / n, vc[1] / n)                      # plaza-center -> camp = clock 2:15

    def rot_cw(vec, deg):                            # clockwise seen from above
        r = math.radians(deg)
        c, s = math.cos(r), math.sin(r)
        return (vec[0] * c - vec[1] * s, vec[0] * s + vec[1] * c)

    vman = rot_cw(vc, -67.5)                         # 2:15 back to 12:00 = the Man
    ring = rot_cw(vman, 90)                          # B ring tangent at the plaza
    # sanity: the drawn B-street lot edge should parallel the derived B ring
    be = (to_world(v[3])[0] - to_world(v[2])[0], to_world(v[3])[1] - to_world(v[2])[1])
    nb = math.hypot(*be)
    skew = math.degrees(math.acos(min(1, abs((be[0] * ring[0] + be[1] * ring[1]) / nb))))
    print(f'plaza clock check: B-street edge vs derived B-ring tangent skew {skew:.1f} deg')

    plaza = {'c': [round(pc[0], 3), round(pc[1], 3)],
             'r': round(lot_polygon.arc['r'] / UNITS_PER_FT * FT, 3),
             'man': [round(vman[0], 5), round(vman[1], 5)],
             'ring': [round(ring[0], 5), round(ring[1], 5)],
             'man_dist_m': 950,
             'note': "plaza rim = the frontage arc's circle (75 ft); camp @ 2:15; "
                     'Man ~950 m down the 4:30 radial (approx B-ring radius)'}

    data = {
        'note': 'generated by sim/tools/camp_from_svg.py from LotHP-26-v3.svg — do not hand-edit',
        'source': SVG.name,
        'anchor': {'hex_svg': [round(v, 3) for v in hex_svg],
                   'axis_svg': [round(v, 5) for v in ax],
                   'hex_world': [10.044, 1.26],
                   'note': 'drawing maze hex centroid -> maze_layout hex_center; '
                           'maze axis -> +x, plaza/street -> +z; 1 svg unit = 1 ft/2.83465'},
        'address': '4:30 & B (plaza)',
        'frontage': {'plaza_ft': 50, 'b_street_ft': 175, 'neighbor_ft': 150, 'bds_ft': 100},
        'lot': [[round(x, 3), round(z, 3)] for x, z in lot],
        'edges': edges,
        'plaza': plaza,
        'zones': zones,
        'items': items,
    }
    OUT.write_text('// generated by sim/tools/camp_from_svg.py from LotHP-26-v3.svg'
                   ' — do not hand-edit\nwindow.CAMP_DATA = '
                   + json.dumps(data, separators=(',', ':')) + ';\n')
    print(f'wrote {OUT.relative_to(ROOT)}: lot {len(lot)} pts, '
          f'{len(zones)} zones, {len(items)} items')
    for z in zones:
        print(f"  zone {z['key']:9s} {z['w']/FT:5.1f}x{z['d']/FT:5.1f} ft  at ({z['cx']:6.2f},{z['cz']:6.2f})  rot {math.degrees(z['rot']):6.1f}deg")
    for i in items:
        dim = f"r {i['r']/FT:4.1f} ft" if 'r' in i else f"{i['w']/FT:5.1f}x{i['d']/FT:5.1f} ft"
        print(f"  item {i['kind']:10s} {dim}  at ({i['cx']:6.2f},{i['cz']:6.2f})")


if __name__ == '__main__':
    main()
