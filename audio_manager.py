import json
import logging
import os
import random
from collections import deque

logger = logging.getLogger(__name__)


class AudioManager:
    def __init__(self, config_file='audio_config.json', music_dir='music', rng=None):
        self.config_file = config_file
        self.music_dir = music_dir
        self._rng = rng or random.SystemRandom()
        self.audio_config = self.load_config()
        self._recent = {}  # effect_name -> deque of recently played files (anti-repeat)

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
        """All audio files (effects and music) a client should cache locally."""
        audio_files = []
        for config in self.audio_config['effects'].values():
            audio_files.extend(config.get('audio_files', []))
        return {
            'effects': list(set(audio_files)),
            'music': self.get_background_music_files()
        }

    def get_background_music_files(self):
        if os.path.exists(self.music_dir):
            return [f for f in os.listdir(self.music_dir) if f.endswith('.mp3')]
        logger.warning(f"Music directory not found: {self.music_dir}")
        return []

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
