#!/usr/bin/env python3
"""Export the xTool cut file for the Cuddle projector enclosure.

One SVG, one coordinate frame:
  projector-shroud.svg    shroud (rear = VIVO mount wall) + filter plenum panels
Two colors in one frame (same convention as export.py):
  black = CUT       red = SCORE/etch in XCS
Run from enclosure/:  python3 export-shroud.py
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
SCAD = HERE / 'projector-shroud.scad'

PATH_RE = re.compile(r'<path[^>]*\sd="([^"]+)"[^>]*/?>')
VIEW_RE = re.compile(r'viewBox="([-\d. ]+)"')


def scad_svg(part):
    with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as f:
        out = f.name
    r = subprocess.run(['openscad', '-D', f'part="{part}"', '-o', out, str(SCAD)],
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


def main():
    cut, vb_c = scad_svg('sheet')
    etch, vb_e = scad_svg('sheet_etch')
    vb = union_vb(vb_c, vb_e)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" '
             f'viewBox="{vb[0]} {vb[1]} {vb[2]} {vb[3]}" '
             f'width="{vb[2]}mm" height="{vb[3]}mm">']
    for d in cut:
        parts.append(f'<path d="{d}" fill="none" stroke="black" stroke-width="0.3"/>')
    for d in etch:
        parts.append(f'<path d="{d}" fill="none" stroke="red" stroke-width="0.3"/>')
    parts.append('</svg>')
    out = HERE / 'projector-shroud.svg'
    out.write_text('\n'.join(parts))
    print(f'wrote {out} ({len(cut)} cut paths, {len(etch)} etch paths)')


if __name__ == '__main__':
    main()
