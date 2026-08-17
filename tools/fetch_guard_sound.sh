#!/usr/bin/env bash
# Fetch + master the Legends of the Hidden Temple TEMPLE GUARD sting into
# audio_files/temple-guard-entry.mp3 — the Monkey Room ENTRY cue (radar
# presence -> ShrineGuard effect). Companion to fetch_monkey_sound.sh
# (MonkeyBusiness, the puzzle-win cue).
#
# Source: Jay Lewis's game-show SFX archive (tpirepguide.com) — lotht-guard.wav,
# the sting when a temple guard grabs a player entering a room. A copy of the
# raw sample lives in tools/samples/ so this works offline.
#
# Mastering: 8-bit/11kHz mono source — band-limit the quantization hiss, fade
# the hard 3.0s cut, pad + hall echo so the roar decays like a cave, and
# loudness-normalize. The lighting effect (effects/monkey_shrine.py) is
# hand-synced to THIS render: ambush slam at 0.0s, sustained roar to ~2.85s,
# echo tail out past 4s. If you change the filter chain, re-measure and update
# the effect.
set -euo pipefail
cd "$(dirname "$0")/.."

SRC=tools/samples/lotht-guard.wav
if [ ! -f "$SRC" ]; then
    curl -fsS -o "$SRC" "http://tpirepguide.com/qwizx/gssfx/usa/lotht-guard.wav"
fi

ffmpeg -v error -y -i "$SRC" \
    -af "aresample=44100,highpass=f=70,lowpass=f=5200,afade=t=out:st=2.85:d=0.15,apad=pad_dur=1.4,aecho=0.8:0.55:70|125:0.32|0.18,loudnorm=I=-13:TP=-1.2:LRA=9" \
    -ar 44100 -ac 2 -codec:a libmp3lame -q:a 2 \
    audio_files/temple-guard-entry.mp3

echo "wrote audio_files/temple-guard-entry.mp3"
