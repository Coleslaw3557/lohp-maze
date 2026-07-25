#!/bin/bash
# Bridge-loop driver (2026-07-24 motion rework): full-motion 30s base loops.
#   run_bridge.sh <theme> <anchor.png> <prompt.txt> <seed> a|b|finish
# a:      submit clip A (first_frame=anchor, free-running end)
# b:      extract A's final frame, submit clip B (first=A_last, last=anchor)
# finish: stitch A+B -> base_loop_<theme>_192.npy + preview + sim mp4, print
#         the motion score (mean |frame delta| per px, /255; old bases 0.3-0.8)
set -euo pipefail
cd "$(dirname "$0")"
THEME=$1 ANCHOR=$2 PROMPT=$3 SEED=$4 PHASE=$5
MODEL=${MODEL:-bytedance/seedance-2.0}
# PAIR env ('' default, '2', '3'...) names extra bridge pairs; every pair
# starts AND ends on the anchor, so pairs concatenate via prep_loop --clips
A=clip_${THEME}_m${PAIR:-}A_raw.mp4 B=clip_${THEME}_m${PAIR:-}B_raw.mp4

case $PHASE in
  a) exec python3 submit_seedance.py --model "$MODEL" --size 960x720 \
       --duration 15 --seed "$SEED" --frame "$ANCHOR" \
       --prompt-file "$PROMPT" --no-last-frame --out "$A" ;;
  b) rm -f "/tmp/alast_${THEME}${PAIR:-}"_*.png
     ffmpeg -v error -y -sseof -0.5 -i "$A" -vsync 0 "/tmp/alast_${THEME}${PAIR:-}_%03d.png"
     LAST=$(ls "/tmp/alast_${THEME}${PAIR:-}"_*.png | sort | tail -1)
     cp "$LAST" "anchor_${THEME}_m${PAIR:-}alast.png"
     exec python3 submit_seedance.py --model "$MODEL" --size 960x720 \
       --duration 15 --seed $((SEED + 1)) --frame "anchor_${THEME}_m${PAIR:-}alast.png" \
       --last-frame "$ANCHOR" --prompt-file "$PROMPT" --out "$B" ;;
  finish)
     python3 prep_loop.py --clip "$A" --clip-b "$B" --mid-xfade-s 0.5 \
       --xfade-s 0.75 --speed "${SPEED:-1.0}" \
       --out-npy "base_loop_${THEME}_192.npy" \
       --out-mp4 "base_loop_${THEME}_preview.mp4"
     python3 make_browser_asset.py "base_loop_${THEME}_192.npy" "base_loop_${THEME}.mp4"
     python3 - "$THEME" <<'EOF'
import sys, numpy as np
t = sys.argv[1]
a = np.load(f'base_loop_{t}_192.npy').astype(np.float32)
w = np.abs(np.diff(np.concatenate([a, a[:1]]), axis=0)).mean(axis=(1, 2, 3))
print(f'{t}: {len(a)} frames ({len(a)/20:.1f}s) motion={w.mean():.2f}/255 '
      f'min-frame={w.min():.2f} loop-seam-delta={w[-1]:.2f}')
EOF
     ;;
  *) echo "phase must be a|b|finish" >&2; exit 2 ;;
esac
