#!/usr/bin/env python3
"""Turn the chroma-green walking-tarantula clip into spider_skin.npz:
4 gait frames, keyed, despilled, rotated to face +x, centered, on a
canonical 144px canvas with a 120px leg-tip span. The engine's skin loader
(TempleShow) rotates/scales these into the production sprite format at
init, so behavior (patrol, scurry, lunge, gait advance) is untouched.

Geometry (centroid/span/heading) is measured on an ERODED hard mask inside
a centered analysis window (kills chroma noise at the frame edges); the
sprite itself samples the soft matte so hair/leg edges stay feathered.
Heading = PCA major axis of the mask; the head side is the LIGHTER end
(a tarantula's abdomen outweighs the cephalothorax). If the sheet shows it
walking backward, flip HEAD_SIGN.
"""
import subprocess

import numpy as np
from PIL import Image

CLIP = 'clip_spider_raw.mp4'
CANVAS = 144
SPAN = 120.0
HEAD_SIGN = 1.0
W, H = 752, 560  # probed: the API returns its own size, never trust the request
CX0, CX1, CY0, CY1 = W // 5, W * 4 // 5, H // 5, H * 4 // 5  # centered analysis window


def decode(path):
    p = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'rawvideo',
                        '-pix_fmt', 'rgb24', '-'], capture_output=True, check=True)
    n = len(p.stdout) // (W * H * 3)
    return np.frombuffer(p.stdout[:n * W * H * 3], np.uint8).reshape(n, H, W, 3)


def key(rgb):
    """Green-screen matte + despill. Returns (rgb despilled, soft alpha)."""
    f = rgb.astype(np.float32)
    g = f[..., 1] - np.maximum(f[..., 0], f[..., 2])
    a = np.clip((45.0 - g) / 35.0, 0.0, 1.0)
    out = f.copy()
    out[..., 1] = np.minimum(f[..., 1], np.maximum(f[..., 0], f[..., 2]) * 1.08)
    return out, a


def hard_mask(a):
    """alpha>0.6 inside the analysis window, eroded 2x to kill streak noise."""
    m = np.zeros_like(a, dtype=bool)
    m[CY0:CY1, CX0:CX1] = a[CY0:CY1, CX0:CX1] > 0.6
    for _ in range(2):
        e = m.copy()
        e[1:, :] &= m[:-1, :]
        e[:-1, :] &= m[1:, :]
        e[:, 1:] &= m[:, :-1]
        e[:, :-1] &= m[:, 1:]
        m = e
    return m


def main():
    frames = decode(CLIP)
    print(f"{len(frames)} frames")
    stats = []
    for fr in frames:
        _, a = key(fr)
        m = hard_mask(a)
        stats.append((m.sum(), a, m))
    areas = np.array([s[0] for s in stats], float)
    med = np.median(areas[len(areas) // 4: 3 * len(areas) // 4])
    ok = [i for i, s in enumerate(stats)
          if 0.7 * med < s[0] < 1.4 * med and 10 <= i < len(stats) - 4]
    mid = ok[len(ok) // 2]
    picks = [min(ok, key=lambda i: abs(i - t)) for t in
             (mid - 6, mid - 2, mid + 2, mid + 6)]
    print(f"median mask area {med:.0f}, stable frames {len(ok)}, picks {picks}")

    # heading: legs dominate any PCA, so find the ABDOMEN instead — it is
    # the blob that survives heavy erosion — and point forward away from it
    m = stats[picks[1]][2]
    heavy = m.copy()
    for _ in range(8):
        e = heavy.copy()
        e[1:, :] &= heavy[:-1, :]
        e[:-1, :] &= heavy[1:, :]
        e[:, 1:] &= heavy[:, :-1]
        e[:, :-1] &= heavy[:, 1:]
        heavy = e
    ys, xs = np.nonzero(m)
    hys, hxs = np.nonzero(heavy)
    if len(hxs) < 50:
        raise SystemExit('abdomen erosion left nothing — tune erosion count')
    fx, fy = xs.mean() - hxs.mean(), ys.mean() - hys.mean()
    ang = float(np.arctan2(fy * HEAD_SIGN, fx * HEAD_SIGN))
    print(f"abdomen blob {len(hxs)} px, head at {np.degrees(ang):.0f} deg (screen)")

    yy, xx = np.mgrid[0:CANVAS, 0:CANVAS].astype(np.float32)
    ddx, ddy = xx - CANVAS / 2, yy - CANVAS / 2
    ca, sa = np.cos(ang), np.sin(ang)
    cols, alphas = [], []
    for i in picks:
        _, a = key(frames[i])
        rgb = key(frames[i])[0]
        mk = stats[i][2]
        ys, xs = np.nonzero(mk)
        cx, cy = xs.mean(), ys.mean()
        span_px = max(xs.max() - xs.min(), ys.max() - ys.min()) + 8  # eroded 2x
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
        # edge decontamination: semi-alpha fringe pixels carry despilled-green
        # gray that reads as a pale halo on dark floors — darken them and thin
        # the matte so the fringe dies into the floor instead
        col_s = np.clip(bl(rgb) * (0.55 + 0.45 * a_s)[..., None], 0, 255)
        cols.append(col_s.astype(np.uint8))
        alphas.append((a_s ** 1.5).astype(np.float32))
        print(f"  frame {i}: span {span_px}px area {mk.sum()}")
    np.savez_compressed('spider_skin.npz',
                        col=np.stack(cols), alpha=np.stack(alphas),
                        span=SPAN, canvas=CANVAS)
    sheet = np.concatenate([np.concatenate(
        [c, (a[..., None] * 255).astype(np.uint8).repeat(3, 2)], axis=0)
        for c, a in zip(cols, alphas)], axis=1)
    Image.fromarray(sheet).save('spider_skin_sheet.png')
    print('spider_skin.npz + spider_skin_sheet.png')


if __name__ == '__main__':
    main()
