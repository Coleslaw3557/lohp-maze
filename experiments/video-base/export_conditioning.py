#!/usr/bin/env python3
"""Export the jungle leaf-litter base texture as conditioning stills for
video-model image-to-video generation (the _base video-loop experiment).

960x720 is seedance-2.0-fast's native 4:3 720p size AND an exact 5x of the
production 192x144 grid, so the generated clip downscales by a clean integer
factor. The engine's leaf carpet is resolution-independent (leaf size in
meters, count scaled by area, same seed), so the 960 export is the same art
the 192 production grid shows, sampled finer.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)

from projection_engine import JungleShow  # noqa: E402

layout = json.load(open(os.path.join(REPO, 'sim', 'maze_layout.json')))
for gw, name in ((960, 'jungle_base_960x720.png'),
                 (192, 'jungle_base_192x144.png')):
    eng = JungleShow(layout, grid_w=gw)
    base = np.clip(eng._base, 0, 255).astype(np.uint8)
    Image.fromarray(base).save(os.path.join(HERE, name))
    print(f"{name}: grid {eng.gw}x{eng.gh}, ppm {eng.ppm:.1f}")
