#!/usr/bin/env python3
"""Build enclosure-all-rooms.xs: one XCS canvas per room from the jen fab master.

Reads  node-enclosure-jen.svg   (fab master, 720 px = 254 mm, black cut / red etch)
       enclosure-3mm.xs         (Cop Dodge project: canvas/device/profile templates)
       DMSerifDisplay-Regular.ttf (room-name etch font, matches the XCS built-in)
Writes enclosure-all-rooms.xs   (xcs-workspace-v2 zip, 14 canvases)

Per canvas: full base box + lid (re-parked right of the sheet, on the S1 bed)
+ the room's sensor plate (TOF for Entrance/Exit, mm-wave for the radar
rooms) + the room name as DM Serif Display outlines on the red etch layer,
rotated to read top-to-bottom on the right wall like the USB/AUX labels
(Cop Dodge precedent, cap height 5.59 mm, shrunk to fit long names).

Cuddle Cross is the exception: its canvas is the LD2450 sheet from
node-enclosure-cuddle.svg (scad export, lid nested in-sheet, no plate
system; single tracking radar since 2026-08-20 — the 2410C is gone and the
aperture is standard again), name horizontal on the right wall like Cop Dodge.

Rerun after edits to node-enclosure-jen.svg or node-enclosure-cuddle.svg.
Cop Dodge is excluded (already cut).
"""

import json
import re
import time
import uuid
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SVG = HERE / 'node-enclosure-jen.svg'
CUDDLE_SVG = HERE / 'node-enclosure-cuddle.svg'
TEMPLATE_XS = HERE / 'enclosure-3mm.xs'
TTF = HERE / 'DMSerifDisplay-Regular.ttf'
OUT = HERE / 'enclosure-all-rooms.xs'
TEMPLATE_CANVAS = '16d47371-af3b-40ff-8b79-34a27d38d1f7'

PX2MM = 254.0 / 720.0  # 72 dpi art
CUDDLE_DX, CUDDLE_DY = 6.0, 176.0  # scad viewBox y is -170..0; park at (6,6)

# room -> sensor plate (13 radar + Entrance/Exit ToF; Cop Dodge already cut;
# 'cuddle' = the LD2450-only sheet instead of the jen box — different window
# etch, standard aperture since 2026-08-20)
ROOMS = [
    ('Entrance', 'tof'),
    ('Gate', 'mmwave'),
    ('Photo Bomb Room', 'mmwave'),
    ('Porto Room', 'mmwave'),
    ('Bike Lock Room', 'mmwave'),
    ('Guy Line Climb', 'mmwave'),
    ('Monkey Room', 'mmwave'),
    ('No Friends Monday', 'mmwave'),
    ('Sparkle Pony Room', 'mmwave'),
    ('Vertical Moop March', 'mmwave'),
    ('Deep Playa Handshake', 'mmwave'),
    ('Temple Room', 'mmwave'),
    ('Cuddle Cross', 'cuddle'),
    ('Exit', 'tof'),
]

BLACK_CLASSES = {'st0', 'st5', 'st6'}   # cut strokes
RED_CLASSES = {'st1'}                   # etch strokes
LEGEND_CLASSES = {'st2', 'st3', 'st4'}  # colour-key fills below the sheet

NUM = r'-?\d+\.?\d*(?:e-?\d+)?'

# ---------------------------------------------------------------- svg parse

def parse_shapes():
    text = SVG.read_text()
    shapes = []  # (kind, cls, pts[(x,y) mm])
    for m in re.finditer(r'<(polygon|rect|text)\b([^>]*?)/?>', text):
        tag, attrs = m.group(1), m.group(2)
        cls_m = re.search(r'class="([^"]+)"', attrs)
        cls = cls_m.group(1).split()[0] if cls_m else ''
        if tag == 'text':
            shapes.append(('text', cls, []))
            continue
        if tag == 'polygon':
            pts_raw = re.search(r'points="([^"]+)"', attrs).group(1)
            nums = [float(v) for v in re.split(r'[\s,]+', pts_raw.strip()) if v]
            pts = [(nums[i] * PX2MM, nums[i + 1] * PX2MM) for i in range(0, len(nums), 2)]
        else:  # rect
            x = float(re.search(r'\bx="([^"]+)"', attrs).group(1))
            y = float(re.search(r'\by="([^"]+)"', attrs).group(1))
            w = float(re.search(r'width="([^"]+)"', attrs).group(1))
            h = float(re.search(r'height="([^"]+)"', attrs).group(1))
            pts = [(x * PX2MM, y * PX2MM), ((x + w) * PX2MM, y * PX2MM),
                   ((x + w) * PX2MM, (y + h) * PX2MM), (x * PX2MM, (y + h) * PX2MM)]
        shapes.append((tag, cls, pts))
    return shapes


def bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def parse_cuddle():
    """node-enclosure-cuddle.svg (export.py product): one compound cut path +
    one compound etch path, absolute M/L/z, true mm, y in -170..0. Returns
    [(is_red, pts)] shifted to (CUDDLE_DX, CUDDLE_DY)."""
    text = CUDDLE_SVG.read_text()
    paths = re.findall(r'<path[^>]*\sd="([^"]+)"', text)
    assert len(paths) == 2, 'expected exactly cut + etch paths'
    shapes = []
    for is_red, d in ((False, paths[0]), (True, paths[1])):
        for chunk in re.split(r'(?=M)', d.replace('\n', ' ')):
            chunk = chunk.strip()
            if not chunk.startswith('M'):
                continue
            nums = [float(v) for v in re.findall(NUM, re.sub(r'[MLz]', ' ', chunk))]
            pts = [(nums[i] + CUDDLE_DX, nums[i + 1] + CUDDLE_DY)
                   for i in range(0, len(nums), 2)]
            shapes.append((is_red, pts))
    return shapes


def partition(shapes):
    """base / lid / tof / mmwave keep their shapes; legend + annotation text drop."""
    out = {'base': [], 'lid': [], 'tof': [], 'mmwave': [], 'legend': [], 'text': []}
    for tag, cls, pts in shapes:
        if tag == 'text':
            out['text'].append((cls, pts))
            continue
        if cls in LEGEND_CLASSES:
            out['legend'].append((cls, pts))
            continue
        x0, y0, x1, y1 = bbox(pts)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        if y0 < -1:                        # lid parks above the viewBox
            out['lid'].append((cls, pts))
        elif cy > 248:                     # assembly/colour bars below the sheet
            out['legend'].append((cls, pts))
        elif cx > 178 and 164 < cy < 206.5:
            out['tof'].append((cls, pts))
        elif cx > 178 and 206.5 <= cy < 248:
            out['mmwave'].append((cls, pts))
        else:
            out['base'].append((cls, pts))
    return out

# ------------------------------------------------------------------- glyphs

from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen

_font = TTFont(TTF)
_glyphset = _font.getGlyphSet()
_cmap = _font.getBestCmap()
# Cop Dodge text was fontSize 24 * scale 1/3 with the XCS build of the font
# (capHeight 698.5/1000 em) -> cap 5.588 mm. This TTF revision has capHeight
# 660/1000, so scale by cap height, not by em.
CAP_MM = 16.764 / 3
_cap_units = _font['OS/2'].sCapHeight


def _glyph_segments(glyph_name):
    """Glyph outline as [(op, points)] in font units, components decomposed.
    qCurveTo point runs keep their TrueType form (all points explicit after
    inserting implied on-curves during serialisation)."""
    pen = DecomposingRecordingPen(_glyphset)
    _glyphset[glyph_name].draw(pen)
    return pen.value


def _serialise(segments, tf):
    """Segments -> absolute M/L/Q/C/Z dPath, applying point transform tf.
    TrueType qCurveTo runs with several off-curve points get their implied
    on-curve midpoints inserted; a trailing None (all-off-curve contour)
    closes onto the first off-curve's midpoint chain start."""
    def f(p):
        x, y = tf(*p)
        return f'{x:.3f} {y:.3f}'

    parts = []
    for op, pts in segments:
        if op == 'moveTo':
            parts.append('M' + f(pts[0]))
        elif op == 'lineTo':
            parts.append('L' + f(pts[0]))
        elif op == 'curveTo':
            for i in range(0, len(pts), 3):
                parts.append('C' + ' '.join(f(p) for p in pts[i:i + 3]))
        elif op == 'qCurveTo':
            ps = list(pts)
            if ps[-1] is None:          # all-off-curve contour (rare)
                start = ((ps[0][0] + ps[-2][0]) / 2, (ps[0][1] + ps[-2][1]) / 2)
                parts.append('M' + f(start))
                ps[-1] = start
            offs, last = ps[:-1], ps[-1]
            for a, b in zip(offs, offs[1:]):
                mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                parts.append('Q' + f(a) + ' ' + f(mid))
            if offs:
                parts.append('Q' + f(offs[-1]) + ' ' + f(last))
            else:
                parts.append('L' + f(last))
        elif op in ('closePath', 'endPath'):
            parts.append('Z')
    return ''.join(parts)


def name_path(name, max_len_mm, cx, cy=None, top_y=None, rotate=True):
    """Room name as one compound dPath. rotate=True bakes the 90 deg CW turn
    (reads top-to-bottom, letter tops toward the lid edge, like USB/AUX on the
    jen sheet) and centres the run on (cx, cy). rotate=False keeps it
    horizontal (for the scad-layout cuddle sheet), centred on cx with the
    outline top at top_y (Cop Dodge anchoring)."""
    scale_mm = CAP_MM / _cap_units
    adv = 0
    placed = []
    for ch in name.upper():
        if ch == ' ':
            adv += _font['hmtx'][_cmap[32]][0]
            continue
        g = _cmap[ord(ch)]
        placed.append((g, adv))
        adv += _font['hmtx'][g][0]
    s = scale_mm * min(1.0, max_len_mm / (adv * scale_mm))
    x_shift = -adv * s / 2

    # pass 1: all segments into the origin frame (advance-centred run)
    segments = []
    for g, off in placed:
        dx = off * s + x_shift
        if rotate:  # scale + y-flip + advance, then (x, y) -> (-y, x)
            tf = lambda x, y, dx=dx: (y * s, x * s + dx)
        else:
            tf = lambda x, y, dx=dx: (x * s + dx, -y * s)
        for op, pts in _glyph_segments(g):
            segments.append((op, [p and tf(*p) for p in pts]))

    # pass 2: translate into place and serialise
    if rotate:
        tx, ty = cx, cy
    else:
        top = min(p[1] for _, pts in segments for p in pts if p)
        tx, ty = cx, top_y - top
    return _serialise(segments, lambda x, y: (x + tx, y + ty))

# ---------------------------------------------------------------- displays

def dpath_bbox(d):
    nums = [float(v) for v in re.findall(NUM, re.sub(r'[MLQCZz]', ' ', d))]
    return min(nums[0::2]), min(nums[1::2]), max(nums[0::2]), max(nums[1::2])


def poly_dpath(pts):
    return 'M' + 'L'.join(f'{x:.3f} {y:.3f}' for x, y in pts) + 'Z'


def make_display(dpath, red, z, compound=False):
    x0, y0, x1, y1 = dpath_bbox(dpath)
    layer = '#fe0002' if red else '#000000'
    return {
        'id': str(uuid.uuid4()), 'name': None, 'type': 'PATH',
        'x': round(x0, 6), 'y': round(y0, 6), 'angle': 0,
        'scale': {'x': 1, 'y': 1}, 'skew': {'x': 0, 'y': 0},
        'pivot': {'x': 0, 'y': 0}, 'localSkew': {'x': 0, 'y': 0},
        'offsetX': 0, 'offsetY': 0, 'lockRatio': True, 'isClosePath': True,
        'zOrder': z, 'groupTags': [], 'groupTag': str(uuid.uuid4()),
        'layerTag': layer, 'layerColor': layer, 'visible': True,
        'originColor': '#ff0000' if red else '#000000',
        'enableTransform': True, 'visibleState': True, 'lockState': False,
        'resourceOrigin': '',
        'customData': {'tabBreaks': {}, 'startPoint': {}},
        'rootComponentId': '', 'minCanvasVersion': '0.0.0', 'alpha': 1,
        'fill': {'paintType': 'color', 'visible': bool(red),
                 'color': 16711680 if red else 0, 'alpha': 1},
        'stroke': {'paintType': 'color', 'visible': True,
                   'color': 16711680 if red else 0, 'alpha': 1,
                   'width': 0.283465 if red else 0.566929, 'cap': 'butt',
                   'join': 'miter', 'miterLimit': 4, 'alignment': 0.5},
        'effects': [], 'width': round(x1 - x0, 6), 'height': round(y1 - y0, 6),
        'isFill': False, 'lineColor': 16421416, 'fillColor': '#f9932b',
        'points': [], 'fillRule': 'nonzero', 'graphicX': 0, 'graphicY': 0,
        'isCompoundPath': compound, 'dPath': dpath,
    }

# ------------------------------------------------------------------- build

def main():
    shapes = parse_shapes()
    parts = partition(shapes)
    counts = {k: len(v) for k, v in parts.items()}
    print('partition:', counts)
    assert counts['tof'] >= 1 and counts['mmwave'] >= 1 and counts['lid'] >= 1

    # right wall outline (tallest black shape right of the floor) -> name band
    wall = None
    for cls, pts in parts['base']:
        if cls in BLACK_CLASSES:
            x0, y0, x1, y1 = bbox(pts)
            if (x0 + x1) / 2 > 170 and (y1 - y0) > 50:
                assert wall is None, 'more than one right-wall candidate'
                wall = (x0, y0, x1, y1)
    wx0, wy0, wx1, wy1 = wall
    name_cx = wx1 - 12.0                 # empty outer band, clear of edge notches
    name_cy = (wy0 + wy1) / 2
    max_len = (wy1 - wy0) - 14.0         # stay clear of the corner fingers

    # lid: rigid-translate from its off-canvas parking to right of the sheet
    lb = [bbox(pts) for _, pts in parts['lid']]
    lid_dx = 262.0 - min(b[0] for b in lb)
    lid_dy = 8.0 - min(b[1] for b in lb)

    # cuddle sheet: right wall = the 78x39.8 panel whose only interior cut is
    # the Ø9 AUX hole (the left wall holds the Ø24 XLR + DB9 window)
    cuddle_shapes = parse_cuddle()
    cwall = None
    for is_red, pts in cuddle_shapes:
        if is_red:
            continue
        x0, y0, x1, y1 = bbox(pts)
        if abs((x1 - x0) - 78) < 1 and abs((y1 - y0) - 39.8) < 1:
            inner = [bbox(p) for r, p in cuddle_shapes if not r and p is not pts
                     and bbox(p)[0] > x0 and bbox(p)[2] < x1
                     and bbox(p)[1] > y0 and bbox(p)[3] < y1]
            if len(inner) == 1 and abs(inner[0][2] - inner[0][0] - 9) < 1:
                assert cwall is None, 'two cuddle right-wall candidates'
                cwall = (x0, y0, x1, y1)
    assert cwall, 'cuddle right wall not found'

    tz = zipfile.ZipFile(TEMPLATE_XS)
    old_proj = json.loads(tz.read('project.json'))
    old_canvas = json.loads(tz.read(f'canvases/{TEMPLATE_CANVAS}.json'))
    old_dev = json.loads(tz.read('devices/device-MD2-1.json'))
    old_proc = old_dev['processing'][TEMPLATE_CANVAS]

    now = int(time.time() * 1000)
    canvases = []
    for room, plate in ROOMS:
        disp, z = [], 1
        if plate == 'cuddle':
            for is_red, pts in cuddle_shapes:
                disp.append(make_display(poly_dpath(pts), is_red, z)); z += 1
            # Cop Dodge placement: centred on the wall, outline top 7.9 below
            # its top edge, horizontal (the scad sheet lays walls flat)
            d = name_path(room, (cwall[2] - cwall[0]) - 14.0,
                          (cwall[0] + cwall[2]) / 2,
                          top_y=cwall[1] + 7.9, rotate=False)
            disp.append(make_display(d, True, z, compound=True))
        else:
            for cls, pts in parts['base']:
                disp.append(make_display(poly_dpath(pts), cls in RED_CLASSES, z)); z += 1
            for cls, pts in parts['lid']:
                moved = [(x + lid_dx, y + lid_dy) for x, y in pts]
                disp.append(make_display(poly_dpath(moved), cls in RED_CLASSES, z)); z += 1
            for cls, pts in parts[plate]:
                disp.append(make_display(poly_dpath(pts), cls in RED_CLASSES, z)); z += 1
            d = name_path(room, max_len, name_cx, name_cy)
            disp.append(make_display(d, True, z, compound=True))
        canvases.append((str(uuid.uuid4()), room, disp))

    proj = dict(old_proj)
    proj['projectId'] = proj['projectTraceID'] = str(uuid.uuid4())
    proj['projectName'] = 'node-enclosures-all-rooms'
    proj['activeCanvasId'] = canvases[0][0]
    proj['created'] = proj['modify'] = now
    proj['versionInfo'] = dict(old_proj['versionInfo'], savedAt=now)
    proj['schemaMeta'] = dict(old_proj['schemaMeta'], migratedAt=now)
    proj['modules'] = {'canvases': [c[0] for c in canvases], 'devices': ['MD2-1']}
    proj['customProjectData'] = {'projectTraceID': proj['projectId']}

    dev = dict(old_dev)
    dev['processing'] = {}
    for cid, _, _ in canvases:
        block = json.loads(json.dumps(old_proc))
        block['id'] = cid
        dev['processing'][cid] = block

    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('.format', 'v2')
        zf.writestr('meta/persistence-meta.json', tz.read('meta/persistence-meta.json'))
        zf.writestr('project.json', json.dumps(proj))
        zf.writestr('profiles.json', tz.read('profiles.json'))
        zf.writestr('devices/device-MD2-1.json', json.dumps(dev))
        zf.writestr('resources/project-cover.png', tz.read('resources/project-cover.png'))
        zf.writestr('resources/project-cover.png.meta.json',
                    tz.read('resources/project-cover.png.meta.json'))
        for cid, title, disp in canvases:
            cv = json.loads(json.dumps(old_canvas))
            cv['id'] = cid
            cv['title'] = title
            cv['chunkLayout'] = {'displayCount': len(disp), 'chunkCount': 1,
                                 'chunkIndexes': [0]}
            zf.writestr(f'canvases/{cid}.json', json.dumps(cv))
            zf.writestr(f'canvases/{cid}/displays-0.json',
                        json.dumps({'canvasId': cid, 'chunkIndex': 0,
                                    'displays': disp}))

    sizes = sorted({len(d) for _, _, d in canvases})
    print(f'wrote {OUT.name}: {len(canvases)} canvases, '
          f'{"/".join(map(str, sizes))} displays, {OUT.stat().st_size} bytes')


if __name__ == '__main__':
    main()
