import json
import logging
import os
import random
import subprocess
from collections import deque

logger = logging.getLogger(__name__)

DEFAULT_AMBIENCE_PLAYBACK = {
    "loop_under_s": 45.0,
    "loop_for_s": 180.0,
    "once_pad_s": 2.0,
    "unknown_loop": True,
}


class AudioManager:
    def __init__(self, config_file='audio_config.json', rng=None):
        self.config_file = config_file
        self.base_dir = os.path.dirname(os.path.abspath(config_file)) or os.getcwd()
        self._rng = rng or random.SystemRandom()
        self.audio_config = self.load_config()
        self._recent = {}  # effect_name -> deque of recently played files (anti-repeat)
        self._duration_cache = {}

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            logger.info(f"Loaded audio configuration from {self.config_file}")
            return config
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error loading {self.config_file}: {e}")
            return {"effects": {}, "default_volume": 0.7}

    def get_audio_files_to_download(self):
        """All configured effect/ambience files a client should cache locally."""
        audio_files = []
        for config in self.audio_config['effects'].values():
            audio_files.extend(config.get('audio_files', []))
        return {
            'effects': list(set(audio_files)),
        }

    def get_audio_config(self, effect_name):
        config = self.audio_config['effects'].get(effect_name, {})
        if not config:
            logger.warning(f"No audio configuration found for effect: {effect_name}")
        return config

    def get_random_audio_file(self, effect_name):
        config = self.get_audio_config(effect_name)
        audio_files = config.get('audio_files', [])
        if not audio_files:
            return None
        # Optional per-file selection weights (parallel to audio_files, e.g. the
        # pack TRIGGER_MAP.csv suggested_weight column). Absent -> uniform.
        weights = config.get('audio_weights')
        if weights and len(weights) != len(audio_files):
            logger.warning(f"audio_weights length mismatch for {effect_name} "
                           f"({len(weights)} weights vs {len(audio_files)} files); picking uniformly")
            weights = None
        if weights and (any(weight < 0 for weight in weights) or sum(weights) <= 0):
            logger.warning(f"Invalid audio_weights for {effect_name}; picking uniformly")
            weights = None
        # Independent draws feel repetitive, so never replay any of the last
        # len//2 picks for this effect (a 2-file effect strictly alternates).
        history_len = len(audio_files) // 2
        recent = self._recent.get(effect_name)
        if recent is None or recent.maxlen != history_len:
            keep = list(recent)[-history_len:] if (recent and history_len) else []
            recent = deque(keep, maxlen=history_len)
            self._recent[effect_name] = recent
        eligible = [i for i, f in enumerate(audio_files) if f not in recent]
        if not eligible:  # unreachable (history < list size), but never dead-end
            eligible = list(range(len(audio_files)))
        if weights:
            eligible_weights = [weights[i] for i in eligible]
            if sum(eligible_weights) <= 0:
                eligible = [i for i, weight in enumerate(weights) if weight > 0]
                eligible_weights = [weights[i] for i in eligible]
            choice = self._rng.choices(eligible, weights=eligible_weights, k=1)[0]
        else:
            choice = self._rng.choice(eligible)
        picked = audio_files[choice]
        if history_len:
            recent.append(picked)
        return picked

    def _audio_path(self, file_name):
        candidates = [
            os.path.join(self.base_dir, 'audio_files', file_name),
            os.path.join(self.base_dir, file_name),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def get_audio_duration_s(self, file_name):
        """Duration for a configured audio asset, or None when it cannot be read."""
        if file_name in self._duration_cache:
            return self._duration_cache[file_name]
        path = self._audio_path(file_name)
        if not path:
            self._duration_cache[file_name] = None
            return None
        try:
            result = subprocess.run(
                [
                    'ffprobe', '-v', 'error',
                    '-show_entries', 'format=duration',
                    '-of', 'default=nokey=1:noprint_wrappers=1',
                    path,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=3,
            )
            duration = float(result.stdout.strip())
        except (OSError, subprocess.SubprocessError, ValueError) as e:
            logger.warning(f"Could not read audio duration for {file_name}: {e}")
            duration = None
        self._duration_cache[file_name] = duration
        return duration

    def ambience_playback(self, effect_name, file_name, audio_params=None):
        """Loop/rotation policy for ambience beds.

        Short loopable assets repeat for a bounded window; long tracks play once
        and the server rotates the bed after the decoded duration.
        """
        audio_params = audio_params or {}
        config = self.get_audio_config(effect_name)
        policy = dict(DEFAULT_AMBIENCE_PLAYBACK)
        policy.update(self.audio_config.get('ambience_playback') or {})
        policy.update(config.get('ambience_playback') or {})
        duration = self.get_audio_duration_s(file_name)

        explicit_loop = audio_params.get('loop')
        if explicit_loop is None:
            if duration is None:
                loop = bool(policy.get('unknown_loop', True))
            else:
                loop = duration <= float(policy.get('loop_under_s', 45.0))
        else:
            loop = bool(explicit_loop)

        if loop:
            play_for = float(policy.get('loop_for_s', 180.0))
        elif duration is not None:
            play_for = duration + float(policy.get('once_pad_s', 2.0))
        else:
            play_for = float(policy.get('unknown_once_s', policy.get('loop_for_s', 180.0)))

        return {
            'loop': loop,
            'duration_s': round(duration, 3) if duration is not None else None,
            'play_for_s': max(1.0, round(play_for, 3)),
        }
