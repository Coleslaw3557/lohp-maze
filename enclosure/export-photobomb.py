#!/usr/bin/env python3
"""Export the xTool cut files for the Photo Bomb device boxes.

Two SVGs, one per box (one stock/job each), same convention as export.py:
  photobomb-camera-box.svg    C930e webcam box   (~236 x 276 mm)
  photobomb-printer-box.svg   QL-820NWB box      (~300 x 805 mm; rows are
                              grouped to fit a ~430x390 bed load each —
                              select per-row in XCS and reposition stock)
Two colors in one frame: black = CUT, red = SCORE/etch in XCS.
Also renders eyeball previews: preview-assembly-*.png (3D) and sheet-*.png
(rasterized merged SVG = the exact XCS ground truth).

Run from enclosure/:  python3 export-photobomb.py
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
SCAD = HERE / 'photobomb-boxes.scad'

PATH_RE = re.compile(r'<path[^>]*\sd="([^"]+)"[^>]*/?>')
VIEW_RE = re.compile(r'viewBox="([-\d. ]+)"')


def scad_svg(box, part):
    with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as f:
        out = f.name
    r = subprocess.run(['openscad', '-D', f'box="{box}"', '-D', f'part="{part}"',
                        '-o', out, str(SCAD)], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f'openscad failed for {box}/{part}:\n{r.stderr}')
    svg = Path(out).read_text()
    Path(out).unlink()
    vb = [float(v) for v in VIEW_RE.search(svg).group(1).split()]
    return [m.group(1) for m in PATH_RE.finditer(svg)], vb


def union_vb(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x, y = min(ax, bx), min(ay, by)
    return [x, y, max(ax + aw, bx + bw) - x, max(ay + ah, by + bh) - y]


def export_box(box):
    cut, vb_c = scad_svg(box, 'sheet')
    etch, vb_e = scad_svg(box, 'sheet_etch')
    vb = union_vb(vb_c, vb_e)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" '
             f'viewBox="{vb[0]} {vb[1]} {vb[2]} {vb[3]}" '
             f'width="{vb[2]}mm" height="{vb[3]}mm">']
    for d in cut:
        parts.append(f'<path d="{d}" fill="none" stroke="black" stroke-width="0.3"/>')
    for d in etch:
        parts.append(f'<path d="{d}" fill="none" stroke="red" stroke-width="0.3"/>')
    parts.append('</svg>')
    out = HERE / f'photobomb-{box}-box.svg'
    out.write_text('\n'.join(parts))
    print(f'wrote {out.name}: {vb[2]:.0f} x {vb[3]:.0f} mm '
          f'({len(cut)} cut, {len(etch)} etch paths)')
    return out


def preview(box, svg_path):
    png = HERE / f'preview-assembly-photobomb-{box}.png'
    r = subprocess.run(['xvfb-run', '-a', 'openscad',
                        '-D', f'box="{box}"', '-D', 'part="assembly"',
                        '--autocenter', '--viewall', '--imgsize=1400,1000',
                        '-o', str(png), str(SCAD)], capture_output=True, text=True)
    print(f'wrote {png.name}' if r.returncode == 0 else
          f'assembly preview failed for {box}: {r.stderr[-400:]}')
    sheet_png = HERE / f'sheet-photobomb-{box}.png'
    r = subprocess.run(['convert', '-density', '150', str(svg_path), str(sheet_png)],
                       capture_output=True, text=True)
    print(f'wrote {sheet_png.name}' if r.returncode == 0 else
          f'sheet raster failed for {box}: {r.stderr[-400:]}')


def main():
    for box in ('camera', 'printer'):
        svg = export_box(box)
        preview(box, svg)


if __name__ == '__main__':
    main()
