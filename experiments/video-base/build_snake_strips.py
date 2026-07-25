#!/usr/bin/env python3
"""Sample the three-snake chroma plate into per-arc color strips:
top band = rattler, middle = gold, bottom = coral (prompt order), heads at
the RIGHT. For each snake, M median body colors along its length,
head-first. The engine's _snake_style swaps these in as cols_idx — the
capsule rasterizer, width profile, eyes, tongue, and flee behavior stay.
"""
import subprocess

import numpy as np
from PIL import Image

CLIP = 'clip_snakes3.mp4'   # 2026-07-25 plate: tzabcan / cantil / coral
M = 96
KINDS = ('rattler', 'cantil', 'coral')


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                          '-show_entries', 'stream=width,height', '-of', 'csv=p=0',
                          path], capture_output=True, text=True, check=True).stdout
    return tuple(int(v) for v in out.strip().split(','))


def key(rgb):
    f = rgb.astype(np.float32)
    g = f[..., 1] - np.maximum(f[..., 0], f[..., 2])
    a = np.clip((45.0 - g) / 35.0, 0.0, 1.0)
    out = f.copy()
    out[..., 1] = np.minimum(f[..., 1], np.maximum(f[..., 0], f[..., 2]) * 1.08)
    return out, a


W, H = probe(CLIP)
raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', '2', '-i', CLIP,
                      '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                     capture_output=True, check=True).stdout
rgb = np.frombuffer(raw[:W * H * 3], np.uint8).reshape(H, W, 3)
rgbd, a = key(rgb)
mask = a > 0.6

# three horizontal bands split at the row-occupancy gaps
rows = mask.sum(axis=1)
occupied = rows > max(3, W // 200)
edges = np.flatnonzero(np.diff(occupied.astype(int)))
runs = []
start = None
for y in range(H):
    if occupied[y] and start is None:
        start = y
    elif not occupied[y] and start is not None:
        runs.append((start, y))
        start = None
if start is not None:
    runs.append((start, H))
runs = sorted(runs, key=lambda r: r[1] - r[0], reverse=True)[:3]
runs.sort()
print(f"{W}x{H}, bands: {runs}")
if len(runs) != 3:
    raise SystemExit('did not find 3 snake bands — check the plate')

out = {}
strip_img = []
for (y0, y1), kind in zip(runs, KINDS):
    band = mask[y0:y1]
    cols_band = rgbd[y0:y1]
    xs = np.flatnonzero(band.any(axis=0))
    x0, x1 = xs.min(), xs.max()
    strip = np.zeros((M, 3), np.float32)
    # head-first: the plate's heads are at the RIGHT edge
    for i in range(M):
        fx = x1 - (i / (M - 1)) * (x1 - x0)
        sl = slice(max(x0, int(fx) - 2), min(x1 + 1, int(fx) + 3))
        sel = band[:, sl]
        if sel.any():
            strip[i] = np.median(cols_band[:, sl][sel], axis=0)
        else:
            strip[i] = strip[i - 1] if i else (90, 90, 90)
    out[kind] = strip.astype(np.float32)
    strip_img.append(np.repeat(strip[None].astype(np.uint8), 14, axis=0))
    print(f"  {kind}: x {x0}-{x1}, mean rgb {strip.mean(axis=0).round(0)}")

np.savez_compressed('snake_strips.npz', **out)
Image.fromarray(np.concatenate(strip_img, axis=0)).resize((M * 6, 14 * 3 * 4), Image.NEAREST).save('snake_strips_sheet.png')
print('snake_strips.npz + sheet')
