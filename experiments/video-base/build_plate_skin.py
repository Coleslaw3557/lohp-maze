#!/usr/bin/env python3
"""Generic chroma-plate -> skin builder: pull ONE stable frame from a green-
screen clip, key + despill it, center it, and save a single-frame skin npz
(col uint8 (C,C,3), alpha float32 (C,C), span px) the engine's inverse-map
loaders consume. Assumes the subject faces +x per the prompt; --rotate-deg
corrects if the model disobeyed. Used for the monster heads (kukulkan/croc).
"""
import argparse
import subprocess

import numpy as np
from PIL import Image


def probe(path):
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                          '-show_entries', 'stream=width,height',
                          '-of', 'csv=p=0', path],
                         capture_output=True, text=True, check=True).stdout
    w, h = (int(v) for v in out.strip().split(','))
    return w, h


def key(rgb):
    f = rgb.astype(np.float32)
    g = f[..., 1] - np.maximum(f[..., 0], f[..., 2])
    a = np.clip((45.0 - g) / 35.0, 0.0, 1.0)
    out = f.copy()
    out[..., 1] = np.minimum(f[..., 1], np.maximum(f[..., 0], f[..., 2]) * 1.08)
    return out, a


def erode(m, steps):
    for _ in range(steps):
        e = m.copy()
        e[1:, :] &= m[:-1, :]
        e[:-1, :] &= m[1:, :]
        e[:, 1:] &= m[:, :-1]
        e[:, :-1] &= m[:, 1:]
        m = e
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--clip', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--frame-t', type=float, default=2.0)
    ap.add_argument('--rotate-deg', type=float, default=0.0,
                    help='extra rotation if the subject is not facing +x')
    ap.add_argument('--canvas', type=int, default=192)
    ap.add_argument('--span', type=float, default=172.0)
    args = ap.parse_args()

    W, H = probe(args.clip)
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(args.frame_t),
                          '-i', args.clip, '-frames:v', '1',
                          '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True, check=True).stdout
    rgb = np.frombuffer(raw[:W * H * 3], np.uint8).reshape(H, W, 3)
    rgbd, a = key(rgb)
    m = np.zeros_like(a, dtype=bool)
    m[H // 8:H * 7 // 8, W // 8:W * 7 // 8] = a[H // 8:H * 7 // 8, W // 8:W * 7 // 8] > 0.6
    m = erode(m, 2)
    ys, xs = np.nonzero(m)
    if not len(xs):
        raise SystemExit('empty mask — keying failed')
    cx, cy = xs.mean(), ys.mean()
    span_px = max(xs.max() - xs.min(), ys.max() - ys.min()) + 8
    print(f"{args.clip}: {W}x{H}, mask {m.sum()}px, span {span_px}px, "
          f"center ({cx:.0f},{cy:.0f})")

    C, SPAN = args.canvas, args.span
    ang = np.radians(args.rotate_deg)
    ca, sa = np.cos(ang), np.sin(ang)
    yy, xx = np.mgrid[0:C, 0:C].astype(np.float32)
    ddx, ddy = xx - C / 2, yy - C / 2
    s = span_px / SPAN
    sx = cx + (ddx * ca - ddy * sa) * s
    sy = cy + (ddx * sa + ddy * ca) * s
    x0 = np.clip(np.floor(sx).astype(int), 0, W - 2)
    y0 = np.clip(np.floor(sy).astype(int), 0, H - 2)
    fx = np.clip(sx - x0, 0, 1)[..., None]
    fy = np.clip(sy - y0, 0, 1)[..., None]

    def bl(img):
        im = img if img.ndim == 3 else img[..., None]
        return (im[y0, x0] * (1 - fx) * (1 - fy) + im[y0, x0 + 1] * fx * (1 - fy)
                + im[y0 + 1, x0] * (1 - fx) * fy + im[y0 + 1, x0 + 1] * fx * fy)

    a_s = np.clip(bl(a)[..., 0], 0, 1)
    col_s = np.clip(bl(rgbd) * (0.55 + 0.45 * a_s)[..., None], 0, 255)
    np.savez_compressed(args.out, col=col_s.astype(np.uint8),
                        alpha=(a_s ** 1.5).astype(np.float32),
                        span=SPAN, canvas=C)
    sheet = np.concatenate([col_s.astype(np.uint8),
                            (a_s[..., None] * 255).astype(np.uint8).repeat(3, 2)], axis=1)
    Image.fromarray(sheet).save(args.out.replace('.npz', '_sheet.png'))
    print(f"{args.out} + sheet")


if __name__ == '__main__':
    main()
