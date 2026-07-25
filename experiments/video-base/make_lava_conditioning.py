#!/usr/bin/env python3
"""Build the lava conditioning frame: a real frame of the current lava clip
with the ENGINE'S stone layout (production seed, exact positions) composited
as dark immovable basalt boulders, plus the mast-island boulder. Image-to-
video with this as first AND last frame makes the generated melt part around
the stones while the engine draws its live gray numbered stones on top at
the same coordinates — sink/rise interactivity intact (the sunk spot gets a
sustained melt glow so the baked boulder never ghosts through).

Boulders are drawn 0.88x so the engine sprite fully occludes them, and
darkened so anything peeking out reads as crusted rock, not a second stone.
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)

from projection_engine import THEMES  # noqa: E402

GW = 960          # output canvas: 960x720, the deck rect at 4:3
GW_ENGINE = 256   # layout truth: stone placement is world-space at 192/256
K = GW / GW_ENGINE  # (they agree to ~1 cm) but _snap_interior's max_r is in
                    # PIXELS, so a 960 engine seats a DIFFERENT, smaller chain
GH = 720

layout = json.load(open(os.path.join(REPO, 'sim', 'maze_layout.json')))
eng = THEMES['lava'](layout, grid_w=GW_ENGINE)

raw = subprocess.run(
    ['ffmpeg', '-v', 'error', '-ss', '6', '-i',
     os.path.join(HERE, 'clip_lava_raw.mp4'), '-frames:v', '1',
     '-vf', f'scale={GW}:{GH}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
    capture_output=True, check=True).stdout
frame = np.frombuffer(raw[:GW * GH * 3], np.uint8).reshape(GH, GW, 3).astype(np.float32)


def blit(col, alpha, cx, cy, scale=0.88, darken=0.5):
    cx, cy = cx * K, cy * K
    h, w = alpha.shape[:2]
    sh, sw = int(h * K * scale), int(w * K * scale)
    ci = np.asarray(Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)).resize((sw, sh), Image.BILINEAR), np.float32)
    ai = np.asarray(Image.fromarray((alpha[..., 0] * 255).astype(np.uint8)).resize((sw, sh), Image.BILINEAR), np.float32)[..., None] / 255.0
    x0, y0 = int(round(cx - sw / 2)), int(round(cy - sh / 2))
    sx0, sy0 = max(0, -x0), max(0, -y0)
    x0c, y0c = max(0, x0), max(0, y0)
    x1, y1 = min(GW, x0 + sw), min(GH, y0 + sh)
    if x1 <= x0c or y1 <= y0c:
        return
    a = ai[sy0:sy0 + y1 - y0c, sx0:sx0 + x1 - x0c]
    c = ci[sy0:sy0 + y1 - y0c, sx0:sx0 + x1 - x0c] * darken
    region = frame[y0c:y1, x0c:x1]
    region[:] = region * (1 - a) + c * a


for s in eng.stones:
    if s.state != 'up':
        continue  # the spare starts sunk — its spot stays open melt
    col, alpha, _ = eng._patches[s.sid]
    blit(col, alpha, s.px, s.py)
icol, ialpha = eng._island
blit(icol, ialpha, eng.mast[0], eng.mast[1], scale=0.95, darken=0.55)

out = np.clip(frame, 0, 255).astype(np.uint8)
Image.fromarray(out).save(os.path.join(HERE, 'lava_conditioned_960.png'))
Image.fromarray(out).resize((640, 480), Image.LANCZOS).save(
    os.path.join(HERE, 'lava_conditioned_640.png'))
print(f"conditioned frames written; {sum(1 for s in eng.stones if s.state == 'up')} boulders + island")
