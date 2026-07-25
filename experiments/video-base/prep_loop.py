#!/usr/bin/env python3
"""Turn a generated clip into the production-format base loop:
20 fps, 192x144 (area downscale), tail->head crossfade for a seamless loop.

--clip-b appends a second clip (the loop BRIDGE: generated with
first_frame = clip A's final frame, last_frame = clip A's conditioning
canvas) with a short crossfade at the junction; the tail->head crossfade
then lands on near-identical canvas frames, so a full-motion 2x-length
loop closes cleanly.

Outputs base_loop_192.npy (uint8, N x 144 x 192 x 3 — what eval_compose.py
and any future renderer hook consume) and a 4x-bilinear preview mp4 played
3x through so the loop seam is judgeable.
"""
import argparse
import os
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def decode(path, w, h, fps, speed=1.0):
    # setpts first: the fps filter then resamples the sped-up stream, so
    # speed=2 halves the runtime and doubles per-frame motion
    cmd = ['ffmpeg', '-v', 'error', '-i', path,
           '-vf', f'setpts=PTS/{speed},fps={fps},scale={w}:{h}:flags=area',
           '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    n = len(raw) // (w * h * 3)
    return np.frombuffer(raw[:n * w * h * 3], np.uint8).reshape(n, h, w, 3)


def encode(frames, path, fps, scale=4):
    h, w = frames.shape[1:3]
    cmd = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
           '-s', f'{w}x{h}', '-r', str(fps), '-i', '-',
           '-vf', f'scale={w * scale}:{h * scale}:flags=bilinear',
           '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    p.stdin.write(frames.tobytes())
    p.stdin.close()
    if p.wait():
        sys.exit('ffmpeg encode failed')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--clip', default=os.path.join(HERE, 'clip_raw.mp4'))
    ap.add_argument('--clip-b', default=None,
                    help='bridge clip appended after --clip (see docstring)')
    ap.add_argument('--clips', default=None,
                    help='comma list of clips folded left-to-right with the '
                         'junction crossfade; overrides --clip/--clip-b. '
                         'Chain bridge PAIRS (each ends on the anchor) to '
                         'extend a loop: A1,B1,A2,B2,...')
    ap.add_argument('--fps', type=int, default=20)
    ap.add_argument('--size', default='192x144')
    ap.add_argument('--xfade-s', type=float, default=1.0)
    ap.add_argument('--mid-xfade-s', type=float, default=0.5,
                    help='crossfade at the clip/clip-b junction')
    ap.add_argument('--speed', type=float, default=1.0,
                    help='time-compress the source(s): 2.0 = twice as fast')
    ap.add_argument('--out-npy', default=os.path.join(HERE, 'base_loop_192.npy'))
    ap.add_argument('--out-mp4', default=os.path.join(HERE, 'base_loop_192_preview.mp4'))
    args = ap.parse_args()

    w, h = (int(v) for v in args.size.split('x'))

    def fold(f, g):
        # junction: f's last m frames fade into g's first m (g frame 0 was
        # conditioned to equal f's final frame, so this only irons decode jitter)
        m = min(int(round(args.mid_xfade_s * args.fps)), len(f) // 3, len(g) // 3)
        b = (np.arange(m, dtype=np.float32) / m)[:, None, None, None]
        mid = f[len(f) - m:] * (1.0 - b) + g[:m] * b
        print(f"junction: {len(f)} + {len(g)} frames, {m}-frame crossfade")
        return np.concatenate([f[:len(f) - m], mid, g[m:]])

    if args.clips:
        parts = [decode(p.strip(), w, h, args.fps, args.speed).astype(np.float32)
                 for p in args.clips.split(',')]
        f = parts[0]
        for g in parts[1:]:
            f = fold(f, g)
    else:
        f = decode(args.clip, w, h, args.fps, args.speed).astype(np.float32)
        if args.clip_b:
            f = fold(f, decode(args.clip_b, w, h, args.fps, args.speed).astype(np.float32))
    k = min(int(round(args.xfade_s * args.fps)), len(f) // 3)
    print(f"decoded {len(f)} frames @{args.fps} fps {w}x{h}, crossfading {k}")
    # loop closure: frame i in [0,k) is tail frame N-k+i fading into head
    # frame i, so the last kept frame (N-k-1) flows into new frame 0
    a = (np.arange(k, dtype=np.float32) / k)[:, None, None, None]
    head = f[:k] * a + f[len(f) - k:] * (1.0 - a)
    loop = np.concatenate([head, f[k:len(f) - k]]).astype(np.uint8)
    np.save(args.out_npy, loop)
    print(f"{args.out_npy}: {loop.shape} ({loop.nbytes/1e6:.1f} MB), "
          f"{len(loop)/args.fps:.1f}s loop")
    encode(np.concatenate([loop, loop, loop]), args.out_mp4, args.fps)
    print(args.out_mp4, '(3 passes, watch the seams)')


if __name__ == '__main__':
    main()
