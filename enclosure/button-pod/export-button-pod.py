#!/usr/bin/env python3
"""Export the xTool cut file for the button pod (button-pod.scad).

One SVG, one stock/job (3mm ply — the node-box sheet):
  button-pod.svg   six panels nested on one ~232 x 170 bed
Two colors in one coordinate frame, same convention as ../export.py:
  black paths = CUT        red paths = ETCH/MARK (score in XCS)
Also renders the eyeball previews: preview-assembly-button-pod.png (3D,
ghost strip/DB9/WAGOs for fit) and sheet-button-pod.png (rasterized
merged SVG = the exact XCS ground truth).

Run from enclosure/button-pod/:  python3 export-button-pod.py
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
SCAD = HERE / 'button-pod.scad'

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


def export_sheet():
    cut_paths, vb = scad_svg('sheet')
    etch_paths, evb = scad_svg('sheet_etch')
    vb = union_vb(vb, evb)
    x, y, w, h = vb
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" '
             f'width="{w:g}mm" height="{h:g}mm" viewBox="{x:g} {y:g} {w:g} {h:g}">']
    parts.append('<g id="cut" fill="none" stroke="#000000" stroke-width="0.2">')
    parts += [f'<path d="{d}"/>' for d in cut_paths]
    parts.append('</g>')
    parts.append('<g id="etch" fill="#ff0000" stroke="#ff0000" stroke-width="0.1">')
    parts += [f'<path d="{d}"/>' for d in etch_paths]
    parts.append('</g>')
    parts.append('</svg>')
    out = HERE / 'button-pod.svg'
    out.write_text('\n'.join(parts))
    print(f'{out.name}: {len(cut_paths)} cut, {len(etch_paths)} etch, '
          f'{w:g} x {h:g} mm')
    return out


def previews(svg_path):
    png = HERE / 'preview-assembly-button-pod.png'
    r = subprocess.run(['xvfb-run', '-a', 'openscad', '-D', 'part="3d"',
                        '--autocenter', '--viewall', '--imgsize=1400,1000',
                        '-o', str(png), str(SCAD)], capture_output=True, text=True)
    print(f'wrote {png.name}' if r.returncode == 0 else
          f'assembly preview failed: {r.stderr[-400:]}')
    sheet_png = HERE / 'sheet-button-pod.png'
    r = subprocess.run(['convert', '-density', '150', str(svg_path), str(sheet_png)],
                       capture_output=True, text=True)
    print(f'wrote {sheet_png.name}' if r.returncode == 0 else
          f'sheet raster failed: {r.stderr[-400:]}')


if __name__ == '__main__':
    previews(export_sheet())
