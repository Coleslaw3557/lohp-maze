#!/usr/bin/env python3
"""Encode a prepped base-loop npy as the browser-served mp4 the sim plays
(single pass, faststart, yuv420p): base_loop_<theme>.mp4."""
import subprocess
import sys

import numpy as np

npy, out = sys.argv[1], sys.argv[2]
l = np.load(npy)
h, w = l.shape[1:3]
p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo',
                      '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-r', '20', '-i', '-',
                      '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p',
                      '-movflags', '+faststart', out], stdin=subprocess.PIPE)
p.stdin.write(l.tobytes())
p.stdin.close()
sys.exit(p.wait())
