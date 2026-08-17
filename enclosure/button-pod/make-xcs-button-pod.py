#!/usr/bin/env python3
"""Build button-pod-8x.xs: the 8-pod xTool S1 cut project, three bed loads.

Reads  button-pod.scad         (geometry — each panel rendered via openscad)
       ../enclosure-3mm.xs     (Cop Dodge project: canvas/device/processing
                                templates — device MD2-1 = Tim's S1)
       ../DMSerifDisplay-Regular.ttf  (room-name etch font, node-box match)
Writes button-pod-8x.xs        (xcs-workspace-v2 zip, 3 canvases)

Each of the 8 RIGHT walls carries its room's name as DM Serif Display
outlines on the red etch layer (the enclosure-all-rooms precedent: names
live in the .xs, the scad/SVG stay universal) — horizontal, cap 5.59 mm,
long names shrink to fit the wall minus the corner fingers. That makes
the right wall the panel that assigns a kit its room, and it gains an
etch-face rule: name OUT at glue-up. All other panels stay
interchangeable between kits.

All 8 pods are identical, so the 48 panels pack as height-matched bands
instead of per-pod sheets — that is the whole wood-saving trick:
  load 1 (~458 x 286): 3 rows of 4 plates (7 floors + 5 lids)
                       + 1 row of 4 long walls (fronts)
  load 2 (~476 x 253): 1 row of 2 lids + 5 ROTATED right walls (blank,
                       no etch -> safe to rotate; 39.8 wide x 78 tall
                       fills the plate row's leftover width)
                       + 3 mixed rows (2 long + 3 short walls)
                       + 1 row of 4 backs
  load 3 (~236 x 178): the Vertical Moop March pod (2026-08-16 puck
                       revert — 8th room). Loads 1/2 keep the proven
                       7-pod packing byte-for-byte; the add-on rides
                       its own small sheet: floor+lid row, front+back
                       row, left+right row (the named right wall).
4mm part gaps, 6mm sheet margin, everything inside the S1's 498 x 319.
Black layer = cut, red = etch/score; processing blocks are cloned from
the template per canvas, so Tim's proven 3mm-ply settings apply as-is.
Wood labeling = the panels' own etch layers (numerals, BTN POD, DB9,
TERM BLOCK zones, VELCRO/ZIP) — every etched mark rides along.

Rerun after editing button-pod.scad:  python3 make-xcs-button-pod.py
"""

import json
import re
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCAD = HERE / 'button-pod.scad'
TEMPLATE_XS = HERE.parent / 'enclosure-3mm.xs'
TTF = HERE.parent / 'DMSerifDisplay-Regular.ttf'
OUT = HERE / 'button-pod-8x.xs'
TEMPLATE_CANVAS = '16d47371-af3b-40ff-8b79-34a27d38d1f7'

# the 8 port-A rooms (db9-field-wiring.md), one pod each; assigned to the
# right walls in placement order (Vertical Moop March last = the load-3
# right wall, added 2026-08-16 with the puck revert)
ROOMS = ['Gate', 'Deep Playa Handshake', 'Bike Lock Room',
         'No Friends Monday', 'Photo Bomb Room', 'Monkey Room',
         'Porto Room', 'Vertical Moop March']

NUM = r'-?\d+\.?\d*(?:e-?\d+)?'
MARGIN, GAP = 6.0, 4.0
BED_W, BED_H = 498.0, 319.0          # xTool S1 work area

# expected panel bboxes (sanity gates on the openscad renders)
EXPECT = {'front': (110, 39.8), 'back': (110, 39.8), 'left': (78, 39.8),
          'right': (78, 39.8), 'floor': (110, 78), 'lid': (110, 78)}
HAS_ETCH = {'front', 'back', 'left', 'floor'}

# ------------------------------------------------------------ scad -> loops

def scad_loops(part):
    """Render one scad part to SVG and split its compound path into loops
    (openscad 2D output is pure M/L/z polylines — text is tessellated)."""
    with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as f:
        out = f.name
    r = subprocess.run(['openscad', '-D', f'part="{part}"', '-o', out, str(SCAD)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f'openscad failed for {part}:\n{r.stderr}')
    text = Path(out).read_text()
    Path(out).unlink()
    loops = []
    for d in re.findall(r'<path[^>]*\sd="([^"]+)"', text):
        for chunk in re.split(r'(?=M)', d.replace('\n', ' ')):
            chunk = chunk.strip()
            if not chunk.startswith('M'):
                continue
            nums = [float(v) for v in re.findall(NUM, re.sub(r'[MLz]', ' ', chunk))]
            loops.append([(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)])
    return loops


def bbox(loops):
    xs = [x for lp in loops for x, _ in lp]
    ys = [y for lp in loops for _, y in lp]
    return min(xs), min(ys), max(xs), max(ys)


def load_panels():
    """{panel: (w, h, [(is_red, loop)])} — each panel normalised so its CUT
    bbox min corner sits at (0,0); etch shares the model frame so the same
    shift applies (asserted to land inside the outline)."""
    panels = {}
    for name, (ew, eh) in EXPECT.items():
        cut = scad_loops(name)
        x0, y0, x1, y1 = bbox(cut)
        w, h = x1 - x0, y1 - y0
        assert abs(w - ew) < 0.3 and abs(h - eh) < 0.3, \
            f'{name}: got {w:.1f} x {h:.1f}, expected {ew} x {eh}'
        shapes = [(False, [(x - x0, y - y0) for x, y in lp]) for lp in cut]
        if name in HAS_ETCH:
            etch = scad_loops(f'{name}_etch')
            ex0, ey0, ex1, ey1 = bbox(etch)
            assert ex0 >= x0 - 0.1 and ey0 >= y0 - 0.1 and \
                   ex1 <= x1 + 0.1 and ey1 <= y1 + 0.1, f'{name}: etch outside cut'
            shapes += [(True, [(x - x0, y - y0) for x, y in lp]) for lp in etch]
        panels[name] = (w, h, shapes)
    return panels

# ------------------------------------------------------- room-name glyphs
# DM Serif Display outlines, the node-box name-etch machinery
# (make-xcs-all-rooms.py): cap-height scaling because this TTF revision's
# capHeight (660/1000 em) differs from the XCS build the Cop Dodge cap of
# 5.588 mm was measured against.

from fontTools.ttLib import TTFont
from fontTools.pens.recordingPen import DecomposingRecordingPen

_font = TTFont(TTF)
_glyphset = _font.getGlyphSet()
_cmap = _font.getBestCmap()
CAP_MM = 16.764 / 3
_cap_units = _font['OS/2'].sCapHeight


def _glyph_segments(glyph_name):
    pen = DecomposingRecordingPen(_glyphset)
    _glyphset[glyph_name].draw(pen)
    return pen.value


def _serialise(segments, tf):
    """Segments -> absolute M/L/Q/Z dPath with point transform tf; TrueType
    qCurveTo runs get their implied on-curve midpoints inserted."""
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
            if ps[-1] is None:
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


def name_segments(name, max_len_mm):
    """Room name as segments in a panel-local frame: horizontal, y-down,
    bbox centred on (0, 0). Cap 5.588 mm, shrunk to fit max_len_mm."""
    scale_mm = CAP_MM / _cap_units
    adv, placed = 0, []
    for ch in name.upper():
        if ch == ' ':
            adv += _font['hmtx'][_cmap[32]][0]
            continue
        g = _cmap[ord(ch)]
        placed.append((g, adv))
        adv += _font['hmtx'][g][0]
    s = scale_mm * min(1.0, max_len_mm / (adv * scale_mm))

    segments = []
    for g, off in placed:
        tf = lambda x, y, dx=off * s: (x * s + dx, -y * s)   # font y-up -> y-down
        for op, pts in _glyph_segments(g):
            segments.append((op, [p and tf(*p) for p in pts]))
    xs = [p[0] for _, pts in segments for p in pts if p]
    ys = [p[1] for _, pts in segments for p in pts if p]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    return [(op, [p and (p[0] - cx, p[1] - cy) for p in pts])
            for op, pts in segments]


def dpath_bbox(d):
    nums = [float(v) for v in re.findall(NUM, re.sub(r'[MLQCZz]', ' ', d))]
    return min(nums[0::2]), min(nums[1::2]), max(nums[0::2]), max(nums[1::2])

# ----------------------------------------------------------------- packing

def placements():
    """[(canvas_index, panel, dx, dy, rot90)] for all 48 panels."""
    put = []

    def row(canvas, y, entries):
        x = MARGIN
        for panel, rot in entries:
            put.append((canvas, panel, x, y, rot))
            w = EXPECT[panel][1] if rot else EXPECT[panel][0]
            x += w + GAP

    # load 1: 3 plate rows + 1 long-wall row
    y = MARGIN
    row(0, y, [('floor', False)] * 4); y += 78 + GAP
    row(0, y, [('floor', False)] * 3 + [('lid', False)]); y += 78 + GAP
    row(0, y, [('lid', False)] * 4); y += 78 + GAP
    row(0, y, [('front', False)] * 4)

    # load 2: plate row (2 lids + 5 rotated rights) + 4 wall rows
    y = MARGIN
    row(1, y, [('lid', False)] * 2 + [('right', True)] * 5); y += 78 + GAP
    row(1, y, [('front', False)] * 2 + [('left', False)] * 3); y += 39.8 + GAP
    row(1, y, [('front', False), ('back', False)] + [('left', False)] * 3)
    y += 39.8 + GAP
    row(1, y, [('back', False)] * 2 +
              [('left', False)] + [('right', False)] * 2); y += 39.8 + GAP
    row(1, y, [('back', False)] * 4)

    # load 3: the 8th pod (Vertical Moop March) on its own small sheet
    y = MARGIN
    row(2, y, [('floor', False), ('lid', False)]); y += 78 + GAP
    row(2, y, [('front', False), ('back', False)]); y += 39.8 + GAP
    row(2, y, [('left', False), ('right', False)])
    return put

# --------------------------------------------------------------- xs writing

def make_display(dpath, red, z, x0, y0, x1, y1, compound=False):
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


def loop_dpath(pts):
    return 'M' + 'L'.join(f'{x:.3f} {y:.3f}' for x, y in pts) + 'Z'


def main():
    panels = load_panels()
    for name, (w, h, shapes) in panels.items():
        print(f'{name}: {w:.1f} x {h:.1f}, {len(shapes)} loops')

    canvas_names = ['pods load 1 (4 fronts, 7 floors, 5 lids)',
                    'pods load 2 (walls + 2 lids)',
                    'pods load 3 (Moop pod)']
    displays = [[], [], []]
    zorders = [1, 1, 1]
    outer = [[], [], []]                   # per-instance bboxes, overlap check
    counts = {}
    rooms = list(ROOMS)                    # consumed by the right walls
    for canvas, panel, dx, dy, rot in placements():
        counts[panel] = counts.get(panel, 0) + 1
        w, h, shapes = panels[panel]
        iw, ih = (h, w) if rot else (w, h)
        for x0, y0, x1, y1 in outer[canvas]:   # no two parts may overlap
            assert dx >= x1 or dx + iw <= x0 or dy >= y1 or dy + ih <= y0, \
                f'overlap on load {canvas + 1} at {dx},{dy} ({panel})'
        outer[canvas].append((dx, dy, dx + iw, dy + ih))
        assert dx + iw <= BED_W - MARGIN + 1e-6 and dy + ih <= BED_H - MARGIN + 1e-6, \
            f'{panel} off the bed on load {canvas + 1}'
        for red, lp in shapes:
            pts = [(h - y + dx, x + dy) for x, y in lp] if rot else \
                  [(x + dx, y + dy) for x, y in lp]
            xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
            displays[canvas].append(make_display(
                loop_dpath(pts), red, zorders[canvas],
                min(xs), min(ys), max(xs), max(ys)))
            zorders[canvas] += 1
        if panel == 'right':               # the room name rides this wall
            segs = name_segments(rooms.pop(0), w - 14.0)
            if rot:                        # name rotates with the panel
                tf = lambda x, y: (h - (y + h / 2) + dx, (x + w / 2) + dy)
            else:
                tf = lambda x, y: (x + w / 2 + dx, y + h / 2 + dy)
            d = _serialise(segs, tf)
            displays[canvas].append(make_display(
                d, True, zorders[canvas], *dpath_bbox(d), compound=True))
            zorders[canvas] += 1
    assert not rooms, f'unassigned rooms: {rooms}'
    assert counts == {p: 8 for p in EXPECT}, f'panel census wrong: {counts}'
    for i, boxes in enumerate(outer):
        x1 = max(b[2] for b in boxes); y1 = max(b[3] for b in boxes)
        print(f'load {i + 1}: {len(boxes)} panels, extent {x1:.1f} x {y1:.1f} mm')

    tz = zipfile.ZipFile(TEMPLATE_XS)
    old_proj = json.loads(tz.read('project.json'))
    old_canvas = json.loads(tz.read(f'canvases/{TEMPLATE_CANVAS}.json'))
    old_dev = json.loads(tz.read('devices/device-MD2-1.json'))
    old_proc = old_dev['processing'][TEMPLATE_CANVAS]

    now = int(time.time() * 1000)
    ids = [str(uuid.uuid4()) for _ in canvas_names]

    proj = dict(old_proj)
    proj['projectId'] = proj['projectTraceID'] = str(uuid.uuid4())
    proj['projectName'] = 'button-pods-8x'
    proj['activeCanvasId'] = ids[0]
    proj['created'] = proj['modify'] = now
    proj['versionInfo'] = dict(old_proj['versionInfo'], savedAt=now)
    proj['schemaMeta'] = dict(old_proj['schemaMeta'], migratedAt=now)
    proj['modules'] = {'canvases': ids, 'devices': ['MD2-1']}
    proj['customProjectData'] = {'projectTraceID': proj['projectId']}

    dev = dict(old_dev)
    dev['processing'] = {}
    for cid in ids:
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
        for cid, title, disp in zip(ids, canvas_names, displays):
            cv = json.loads(json.dumps(old_canvas))
            cv['id'] = cid
            cv['title'] = title
            cv['chunkLayout'] = {'displayCount': len(disp), 'chunkCount': 1,
                                 'chunkIndexes': [0]}
            zf.writestr(f'canvases/{cid}.json', json.dumps(cv))
            zf.writestr(f'canvases/{cid}/displays-0.json',
                        json.dumps({'canvasId': cid, 'chunkIndex': 0,
                                    'displays': disp}))

    print(f'wrote {OUT.name}: {len(ids)} canvases, '
          f'{"/".join(str(len(d)) for d in displays)} displays, '
          f'{OUT.stat().st_size} bytes')

    # eyeball previews: one SVG per load, rasterised beside the .xs
    for i, disp in enumerate(displays):
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{BED_W}mm" '
                 f'height="{BED_H}mm" viewBox="0 0 {BED_W} {BED_H}">',
                 f'<rect width="{BED_W}" height="{BED_H}" fill="white"/>']
        for d in disp:
            col = 'red' if d['layerTag'] == '#fe0002' else 'black'
            parts.append(f'<path d="{d["dPath"]}" fill="none" '
                         f'stroke="{col}" stroke-width="0.3"/>')
        parts.append('</svg>')
        svg = HERE / f'sheet-pods-load{i + 1}.svg'
        svg.write_text('\n'.join(parts))
        subprocess.run(['convert', '-density', '96', str(svg),
                        str(HERE / f'sheet-pods-load{i + 1}.png')], check=False)
        print(f'wrote sheet-pods-load{i + 1}.png')


if __name__ == '__main__':
    main()
