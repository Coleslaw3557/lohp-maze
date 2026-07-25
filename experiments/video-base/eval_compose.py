#!/usr/bin/env python3
"""A/B the video base loop under the REAL reactive engine, renderer untouched.

Two sequential passes with identical seeds (JungleShow default seed +
DemoTracks seed 7 are both deterministic, and jungle behavior never reads
_base), so snakes/walkers/light are frame-identical and the ONLY difference
between panels is the base texture: left = production static leaf carpet,
right = per-frame video base. Panels are upscaled 4x bilinear to stand in
for the VideoCore smoothing scaler, then written side by side at 20 fps.

--selftest runs the chain with a synthetic luminance-ripple loop built from
the static base (plumbing proof, zero credits, deliberately non-art).
"""
import argparse
import json
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)

from projection_engine import JungleShow  # noqa: E402
from projection_renderer import DemoTracks  # noqa: E402

GRID_W = 192
FPS = 20
UP = 4


def run_pass(layout, secs, loop):
    eng = JungleShow(layout, grid_w=GRID_W)
    src = DemoTracks(layout)
    dt = 1.0 / FPS
    frames, cost = [], 0.0
    for i in range(int(secs * FPS)):
        if loop is not None:
            eng._base = loop[i % len(loop)].astype(np.float32)
        t0 = time.perf_counter()
        eng.set_tracks(src.tracks(dt, eng))
        eng.step(dt)
        frames.append(eng.render())
        cost += time.perf_counter() - t0
    print(f"  pass ({'video' if loop is not None else 'static'} base): "
          f"{cost / len(frames) * 1000:.1f} ms/frame mean")
    return frames


def label(img, text):
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 8 + 7 * len(text), 18], fill=(0, 0, 0))
    d.text((4, 3), text, fill=(255, 220, 120))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--loop', default=os.path.join(HERE, 'base_loop_192.npy'))
    ap.add_argument('--secs', type=float, default=40.0)
    ap.add_argument('--out', default=os.path.join(HERE, 'eval_side_by_side.mp4'))
    ap.add_argument('--selftest', action='store_true')
    args = ap.parse_args()

    layout = json.load(open(os.path.join(REPO, 'sim', 'maze_layout.json')))
    if args.selftest:
        base = JungleShow(layout, grid_w=GRID_W)._base
        n = 6 * FPS
        ph = 2 * np.pi * np.arange(n, dtype=np.float32) / n
        x = np.linspace(0, 2 * np.pi, base.shape[1], dtype=np.float32)
        loop = np.clip(base[None] * (1.0 + 0.25 * np.sin(x[None, None, :, None]
                       + ph[:, None, None, None])), 0, 255).astype(np.uint8)
        args.secs = min(args.secs, 12.0)
        tag = 'SELFTEST ripple'
        args.out = os.path.join(HERE, 'eval_selftest.mp4')
    else:
        loop = np.load(args.loop)
        tag = 'video base'
    print(f"loop {loop.shape}, {args.secs:.0f}s eval")

    a = run_pass(layout, args.secs, None)
    b = run_pass(layout, args.secs, loop)

    gh, gw = a[0].shape[:2]
    w2, h2 = gw * UP, gh * UP
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', f'{w2 * 2 + 4}x{h2}', '-r', str(FPS), '-i', '-',
           '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', args.out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    div = np.full((h2, 4, 3), 40, np.uint8)
    for fa, fb in zip(a, b):
        pa = label(Image.fromarray(fa).resize((w2, h2), Image.BILINEAR),
                   'static base (today)')
        pb = label(Image.fromarray(fb).resize((w2, h2), Image.BILINEAR), tag)
        p.stdin.write(np.hstack([np.asarray(pa), div, np.asarray(pb)]).tobytes())
    p.stdin.close()
    if p.wait():
        sys.exit('ffmpeg encode failed')
    print(args.out)


if __name__ == '__main__':
    main()
