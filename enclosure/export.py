#!/usr/bin/env python3
"""Export the xTool cut files from node-enclosure.scad.

Two SVGs, one per stock/job:
  node-enclosure.svg   the six wall panels nested on one bed (3mm ply)
  window-acrylic.svg   the sensor-window panel alone (3mm acrylic)
Both carry two colors in one coordinate frame:
  black paths = CUT        red paths = ETCH/MARK (score or engrave in XCS)
XCS: import, select the red objects -> processing "score" (or engrave),
black -> cut. Run from enclosure/:  python3 export.py
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
SCAD = HERE / 'node-enclosure.scad'
PANELS = ['sheet', 'window']    # ply job + the acrylic window job
HAS_ETCH = {'sheet', 'window'}
OUTNAME = {'sheet': 'node-enclosure.svg', 'window': 'window-acrylic.svg'}
# 14 rooms cut the standard files; Cuddle's 2410C+2450 pair needs the wide
# aperture -> a second pass with cuddle=true, suffixed filenames
VARIANTS = [('', []), ('-cuddle', ['-D', 'cuddle=true'])]

PATH_RE = re.compile(r'<path[^>]*\sd="([^"]+)"[^>]*/?>')
VIEW_RE = re.compile(r'viewBox="([-\d. ]+)"')


def scad_svg(part, defs=()):
    with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as f:
        out = f.name
    r = subprocess.run(['openscad', '-D', f'part="{part}"', *defs, '-o', out, str(SCAD)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f'openscad failed for {part}:\n{r.stderr}')
    svg = Path(out).read_text()
    Path(out).unlink()
    vb = [float(v) for v in VIEW_RE.search(svg).group(1).split()]
    return [m.group(1) for m in PATH_RE.finditer(svg)], vb


def union_vb(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x, y = min(ax, bx), min(ay, by)
    return [x, y, max(ax + aw, bx + bw) - x, max(ay + ah, by + bh) - y]


def write_panel(name, suffix='', defs=()):
    cut_paths, vb = scad_svg(name, defs)
    etch_paths = []
    if name in HAS_ETCH:
        etch_paths, evb = scad_svg(f'{name}_etch', defs)
        vb = union_vb(vb, evb)
    x, y, w, h = vb
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
             f'width="{w:g}mm" height="{h:g}mm" viewBox="{x:g} {y:g} {w:g} {h:g}">']
    parts.append('<g id="cut" fill="none" stroke="#000000" stroke-width="0.2">')
    parts += [f'<path d="{d}"/>' for d in cut_paths]
    parts.append('</g>')
    if etch_paths:
        parts.append('<g id="etch" fill="#ff0000" stroke="#ff0000" stroke-width="0.1">')
        parts += [f'<path d="{d}"/>' for d in etch_paths]
        parts.append('</g>')
    parts.append('</svg>')
    base = OUTNAME.get(name, f'panel-{name}.svg')
    out = HERE / base.replace('.svg', f'{suffix}.svg')
    out.write_text('\n'.join(parts))
    print(f'{out.name}: {len(cut_paths)} cut, {len(etch_paths)} etch, '
          f'{w:g} x {h:g} mm')


if __name__ == '__main__':
    for suffix, defs in VARIANTS:
        for p in PANELS:
            write_panel(p, suffix, defs)
