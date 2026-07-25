#!/usr/bin/env python3
"""Cut a multi-stone chroma plate into a stone-skin stack:
key + despill, find each stone as a connected blob, center/scale each onto
a 96px canvas (88px span), save col (N,96,96,3) uint8 + alpha (N,96,96).
The engine picks frame (stone id % N) and chisels its Mayan numeral into
the generated surface, so every stepping stone wears a different face.

    python3 build_stone_skins.py --clip clip_stones_lava.mp4 --out stone_skin_lava.npz
"""
import argparse
import subprocess

import numpy as np
from PIL import Image

CANVAS, SPAN = 96, 88.0


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


def components(mask, min_area, cap=12):
    """Connected blobs by iterative numpy flood growth (no scipy)."""
    remaining = mask.copy()
    blobs = []
    while remaining.any() and len(blobs) < cap:
        ys, xs = np.nonzero(remaining)
        blob = np.zeros_like(mask)
        blob[ys[0], xs[0]] = True
        while True:
            grown = blob.copy()
            grown[1:, :] |= blob[:-1, :]
            grown[:-1, :] |= blob[1:, :]
            grown[:, 1:] |= blob[:, :-1]
            grown[:, :-1] |= blob[:, 1:]
            grown &= remaining
            if (grown == blob).all():
                break
            blob = grown
        remaining &= ~blob
        if blob.sum() >= min_area:
            blobs.append(blob)
    return blobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--clip', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--frame-t', type=float, default=2.0)
    args = ap.parse_args()

    W, H = probe(args.clip)
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(args.frame_t),
                          '-i', args.clip, '-frames:v', '1', '-f', 'rawvideo',
                          '-pix_fmt', 'rgb24', '-'],
                         capture_output=True, check=True).stdout
    rgb = np.frombuffer(raw[:W * H * 3], np.uint8).reshape(H, W, 3)
    rgbd, a = key(rgb)
    blobs = components(a > 0.6, min_area=(W * H) // 400)
    # stable order: row-major by centroid so stone id -> variant is repeatable
    def ckey(b):
        ys, xs = np.nonzero(b)
        return (round(ys.mean() / (H / 3)), xs.mean())
    blobs.sort(key=ckey)
    print(f"{args.clip}: {W}x{H}, {len(blobs)} stones")

    yy, xx = np.mgrid[0:CANVAS, 0:CANVAS].astype(np.float32)
    ddx, ddy = xx - CANVAS / 2, yy - CANVAS / 2
    cols, alphas = [], []
    for b in blobs:
        ys, xs = np.nonzero(b)
        cx, cy = xs.mean(), ys.mean()
        span_px = max(xs.max() - xs.min(), ys.max() - ys.min()) + 4
        s = span_px / SPAN
        sx, sy = cx + ddx * s, cy + ddy * s
        x0 = np.clip(np.floor(sx).astype(int), 0, W - 2)
        y0 = np.clip(np.floor(sy).astype(int), 0, H - 2)
        fx = np.clip(sx - x0, 0, 1)[..., None]
        fy = np.clip(sy - y0, 0, 1)[..., None]

        def bl(img):
            im = img if img.ndim == 3 else img[..., None]
            return (im[y0, x0] * (1 - fx) * (1 - fy) + im[y0, x0 + 1] * fx * (1 - fy)
                    + im[y0 + 1, x0] * (1 - fx) * fy + im[y0 + 1, x0 + 1] * fx * fy)

        # mask the sample to THIS blob so neighbors never bleed in
        bm = bl(b.astype(np.float32))[..., 0]
        a_s = np.clip(bl(a)[..., 0], 0, 1) * (bm > 0.4)
        col_s = np.clip(bl(rgbd) * (0.55 + 0.45 * a_s)[..., None], 0, 255)
        cols.append(col_s.astype(np.uint8))
        alphas.append((a_s ** 1.5).astype(np.float32))
    np.savez_compressed(args.out, col=np.stack(cols), alpha=np.stack(alphas),
                        span=SPAN, canvas=CANVAS)
    sheet = np.concatenate(cols, axis=1)
    Image.fromarray(sheet).save(args.out.replace('.npz', '_sheet.png'))
    print(f"{args.out}: {len(cols)} variants + sheet")


if __name__ == '__main__':
    main()
