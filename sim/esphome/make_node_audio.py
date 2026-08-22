#!/usr/bin/env python3
"""Generate the server's streamable effect-cue WAVs (nodes store NO audio).

2026-07-25 (Tim): ALL audio lives on and streams from the server — nothing is
compiled into node firmware. This converts every effect mp3 referenced by
audio_config.json (the base `effects` pools AND the attended-mode
`effects_attended` overrides) to audio_files/cues/<cue_id>.wav — 22.05kHz mono s16 (the
announcement-pipeline format in packages/audio_s3.yaml) with the effect's
per-effect VOLUME BAKED IN, since the node's media_player volume is shared
with the ambience bed. node_audio_manager.py streams them to nodes as
announcement URLs: GET /api/audio/cues/<cue_id>.wav.

Rerun after editing audio_config.json or the mp3s (ffmpeg required):

    sim/esphome/make_node_audio.py
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))
from node_audio_manager import cue_id  # noqa: E402 — single source of cue ids

CUES_DIR = REPO / 'audio_files' / 'cues'


def convert(src, dest, volume):
    subprocess.run(
        ['ffmpeg', '-y', '-loglevel', 'error', '-i', str(src),
         '-ac', '1', '-ar', '22050', '-sample_fmt', 's16',
         '-af', f'volume={volume}', str(dest)],
        check=True)


def main():
    config = json.load(open(REPO / 'audio_config.json'))
    effects_cfg = config['effects']
    CUES_DIR.mkdir(parents=True, exist_ok=True)

    # FLAT MIX (2026-08-22, Tim): every cue bakes at the config's
    # effect_level — the per-effect volume fields are legacy trim, no longer
    # applied (beds bake at ambience_level in remote_host_manager).
    # Attended-mode pool overrides (top-level effects_attended) bake too — a
    # sound-mode flip must find its cue WAVs already on disk.
    effect_level = config.get('effect_level', 0.98)
    try:  # runtime override (data/audio_levels.json — /api/audio_levels)
        effect_level = float(json.load(
            open(REPO / 'data' / 'audio_levels.json'))['effect_level'])
    except (OSError, KeyError, ValueError, TypeError):
        pass
    sources = [(effect, entry, effect_level)
               for effect, entry in effects_cfg.items()]
    sources += [
        (f'{name} (attended)', entry, effect_level)
        for name, entry in (config.get('effects_attended') or {}).items()
        if not name.startswith('_') and isinstance(entry, dict)]

    cues = {}   # cue_id -> (src, volume)
    for effect, entry, volume in sources:
        for fname in entry.get('audio_files', []):
            src = REPO / 'audio_files' / fname
            if not src.exists():
                sys.exit(f"ERROR: {src} missing (effect '{effect}')")
            cue = cue_id(fname)
            if cue in cues and cues[cue] != (src, volume):
                print(f"  WARN: {fname} used by two effects at different "
                      f"volumes — keeping the louder")
                volume = max(volume, cues[cue][1])
            cues[cue] = (src, volume)

    total = 0
    for cue, (src, volume) in sorted(cues.items()):
        dest = CUES_DIR / f'{cue}.wav'
        convert(src, dest, volume)
        total += dest.stat().st_size
        print(f"  {cue}.wav  {dest.stat().st_size // 1024}KB  "
              f"(from {src.name} @ vol {volume})")
    print(f"-> {CUES_DIR}  ({len(cues)} cues, {total // 1024}KB) — "
          f"served at /api/audio/cues/<cue_id>.wav")


if __name__ == '__main__':
    main()
