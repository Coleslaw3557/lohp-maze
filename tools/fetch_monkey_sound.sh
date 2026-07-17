#!/usr/bin/env bash
# Fetch + master the Legends of the Hidden Temple "Shrine of the Silver Monkey
# assembled" cue into audio_files/monkey-shrine-complete.mp3.
#
# Source: Jay Lewis's game-show SFX archive (tpirepguide.com) — lotht-monkhead.wav,
# "heard when the statue in the Shrine of the Silver Monkey is assembled".
# A copy of the raw sample lives in tools/samples/ so this works offline.
#
# Mastering: the archive wav is 8-bit/11kHz mono, so we band-limit away the
# quantization hiss, add a small hall tail so the cue feels bigger in the room,
# and loudness-normalize. The lighting effect (effects/monkey_business.py) is
# hand-synced to THIS render: fanfare hit 0.06s, final stinger 1.56s. If you
# change the filter chain, re-measure the onsets and update the effect.
set -euo pipefail
cd "$(dirname "$0")/.."

SRC=tools/samples/lotht-monkhead.wav
if [ ! -f "$SRC" ]; then
    curl -fsS -o "$SRC" "http://tpirepguide.com/qwizx/gssfx/usa/lotht-monkhead.wav"
fi

ffmpeg -v error -y -i "$SRC" \
    -af "aresample=44100,highpass=f=70,lowpass=f=5200,apad=pad_dur=0.9,aecho=0.8:0.55:70|125:0.32|0.18,loudnorm=I=-13:TP=-1.2:LRA=9" \
    -ar 44100 -ac 2 -codec:a libmp3lame -q:a 2 \
    audio_files/monkey-shrine-complete.mp3

echo "wrote audio_files/monkey-shrine-complete.mp3"
