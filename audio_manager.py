import json
import hashlib
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
    "node_prepare_stream": True,
    "node_prepare_loop": True,
    "node_loop_crossfade_s": 1.0,
    "node_loop_max_copies": 64,
    # Bed track changes fade out/in instead of hard-cutting. Browser/VLC
    # clients ramp at runtime (the value rides the ambience payload); node
    # streams get it baked into the generated MP3's head and tail.
    "fade_s": 2.0,
}

# Global sound modes: 'unattended' (the default walk-through experience) and
# 'attended' (staff running people through fast — short, pointed sounds).
# Attended swaps POOL CONTENTS only, through the audio_config.json top-level
# `effects_attended` overlay; every selection key (maze_ambience,
# room_backgrounds, room_leave_sounds, ambient_oneshots, THEME_SHOWS) is
# mode-shared, and lights/DMX/the floor projector never change with the mode.
SOUND_MODES = ("unattended", "attended")
ATTENDED_KEY = "effects_attended"


class AudioManager:
    def __init__(self, config_file='audio_config.json', rng=None):
        self.config_file = config_file
        self.base_dir = os.path.dirname(os.path.abspath(config_file)) or os.getcwd()
        self._rng = rng or random.SystemRandom()
        self.audio_config = self.load_config()
        # In-memory ON PURPOSE: every boot starts unattended, and a config
        # reload (the console's push) must not reset a live flip.
        self.sound_mode = SOUND_MODES[0]
        self._recent = {}  # (sound_mode, effect_name) -> deque of recent picks (anti-repeat)
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

    def set_sound_mode(self, mode):
        """Switch the global sound mode. Returns True when it changed."""
        if mode not in SOUND_MODES:
            raise ValueError(f"unknown sound mode {mode!r} (choices: {SOUND_MODES})")
        changed = mode != self.sound_mode
        self.sound_mode = mode
        if changed:
            logger.info(f"Sound mode -> {mode}")
        return changed

    def attended_effects(self):
        """The attended-mode pool overrides (top-level `effects_attended`).
        Pools not listed keep tracking `effects` — shared until edited."""
        overlay = self.audio_config.get(ATTENDED_KEY) or {}
        return {name: entry for name, entry in overlay.items()
                if not name.startswith('_') and isinstance(entry, dict)}

    def attended_differs(self, effect_name):
        """True when this pool resolves differently in the two modes — the
        signal a live bed needs a fresh pick after a mode flip."""
        override = self.attended_effects().get(effect_name)
        if override is None:
            return False
        base = self.audio_config['effects'].get(effect_name, {})
        if not base:
            return False  # overlay-only names never resolve; nothing to restart
        return (
            list(override.get('audio_files', [])) != list(base.get('audio_files', []))
            or list(override.get('audio_weights') or []) != list(base.get('audio_weights') or [])
            or override.get('volume', base.get('volume')) != base.get('volume')
        )

    def get_audio_files_to_download(self):
        """All configured effect/ambience files a client should cache locally.
        BOTH modes' files, always — a sound-mode flip must never wait on a
        download."""
        audio_files = []
        for config in self.audio_config['effects'].values():
            audio_files.extend(config.get('audio_files', []))
        for config in self.attended_effects().values():
            audio_files.extend(config.get('audio_files', []))
        return {
            'effects': list(set(audio_files)),
        }

    def get_audio_config(self, effect_name):
        config = self.audio_config['effects'].get(effect_name, {})
        if not config:
            logger.warning(f"No audio configuration found for effect: {effect_name}")
            return config
        if self.sound_mode == 'attended':
            override = self.attended_effects().get(effect_name)
            if override is not None:
                # audio_files/audio_weights swap in AS A PAIR (base weights
                # against override files would be a length-mismatched lie);
                # volume rides along only if the override sets one; playback
                # policy and comments stay with the base entry.
                merged = {key: value for key, value in config.items()
                          if key not in ('audio_files', 'audio_weights')}
                merged['audio_files'] = list(override.get('audio_files', []))
                if override.get('audio_weights'):
                    merged['audio_weights'] = list(override['audio_weights'])
                if 'volume' in override:
                    merged['volume'] = override['volume']
                return merged
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
        history_key = (self.sound_mode, effect_name)
        recent = self._recent.get(history_key)
        if recent is None or recent.maxlen != history_len:
            keep = list(recent)[-history_len:] if (recent and history_len) else []
            recent = deque(keep, maxlen=history_len)
            self._recent[history_key] = recent
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

    def _generated_loop_name(self, file_name, play_for_s, crossfade_s, gain, fade_s):
        path = self._audio_path(file_name)
        if not path:
            return None, None
        try:
            stat = os.stat(path)
        except OSError:
            return None, None
        key = "|".join([
            file_name,
            str(stat.st_mtime_ns),
            str(stat.st_size),
            f"{play_for_s:.3f}",
            f"{crossfade_s:.3f}",
            f"gain{gain:.3f}",
            f"fade{fade_s:.3f}",
        ])
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
        stem = os.path.splitext(os.path.basename(file_name))[0]
        safe_stem = "".join(c if c.isalnum() else "_" for c in stem).strip("_")[:48]
        rel = os.path.join("generated", "ambience_loops",
                           f"{safe_stem or 'loop'}_{digest}.mp3")
        return path, rel

    def _generated_node_stream_name(self, file_name, gain, fade_desc=""):
        path = self._audio_path(file_name)
        if not path:
            return None, None
        try:
            stat = os.stat(path)
        except OSError:
            return None, None
        key = "|".join([
            file_name,
            str(stat.st_mtime_ns),
            str(stat.st_size),
            f"node-mono-44100-mp3-v2-gain{gain:.3f}{fade_desc}",
        ])
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
        stem = os.path.splitext(os.path.basename(file_name))[0]
        safe_stem = "".join(c if c.isalnum() else "_" for c in stem).strip("_")[:48]
        rel = os.path.join("generated", "node_streams",
                           f"{safe_stem or 'stream'}_{digest}.mp3")
        return path, rel

    def _node_policy(self, effect_name):
        config = self.get_audio_config(effect_name)
        policy = dict(DEFAULT_AMBIENCE_PLAYBACK)
        policy.update(self.audio_config.get("ambience_playback") or {})
        policy.update(config.get("ambience_playback") or {})
        return policy

    @staticmethod
    def _stream_fade_s(playback, policy, cap_s):
        """The track-change fade baked into a generated node stream, clamped so
        short assets aren't all edge. Below 50 ms it rounds to no fade."""
        try:
            fade_s = float(playback.get("fade_s", policy.get("fade_s", 0.0)) or 0.0)
        except (TypeError, ValueError):
            fade_s = 0.0
        fade_s = max(0.0, min(fade_s, cap_s))
        return round(fade_s, 3) if fade_s >= 0.05 else 0.0

    def prepare_node_ambience_loop(self, effect_name, file_name, playback, gain=1.0):
        """Create a cached, longer crossfaded bed for ESP32 node playback.

        ESPHome's speaker media player does not expose a real repeat/crossfade
        primitive. For short ambience assets, make one longer MP3 with
        crossfaded joins and let the node stream it once; any remaining restart
        boundary happens minutes apart instead of every source-file duration.
        Browser clients still receive the original file and loop locally.

        `gain` (the bed pool's volume) is baked into the generated audio: the
        node's media_player entity volume is shared with the announcement
        pipeline, so beds must arrive pre-attenuated (node_audio_manager).
        """
        if not playback.get("loop"):
            return None
        policy = self._node_policy(effect_name)
        if not policy.get("node_prepare_loop", True):
            return None
        try:
            duration_s = float(playback.get("duration_s") or 0)
            play_for_s = float(playback.get("play_for_s") or 0)
            crossfade_s = float(policy.get("node_loop_crossfade_s", 1.0))
            max_copies = int(policy.get("node_loop_max_copies", 64))
        except (TypeError, ValueError):
            return None
        if duration_s <= 0 or play_for_s <= duration_s:
            return None
        crossfade_s = min(crossfade_s, max(0.0, duration_s / 3.0))
        if crossfade_s < 0.1:
            return None
        fade_s = self._stream_fade_s(playback, policy, play_for_s / 4.0)
        step_s = duration_s - crossfade_s
        copies = int((play_for_s + crossfade_s + step_s - 0.001) // step_s) + 1
        copies = max(2, copies)
        if copies > max_copies:
            logger.info(f"Node ambience loop prep skipped for {file_name}: "
                        f"{copies} copies exceeds cap {max_copies}")
            return None
        source_path, rel_name = self._generated_loop_name(file_name, play_for_s,
                                                          crossfade_s, gain, fade_s)
        if not source_path or not rel_name:
            return None
        out_path = os.path.join(self.base_dir, "audio_files", rel_name)
        if os.path.exists(out_path):
            return rel_name
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        inputs = []
        labels = []
        for i in range(copies):
            inputs.extend(["-i", source_path])
            labels.append(f"a{i}")
        filters = [
            f"[{i}:a]aformat=channel_layouts=mono,aresample=44100[{labels[i]}]"
            for i in range(copies)
        ]
        current = labels[0]
        for i in range(1, copies):
            out = f"x{i}"
            filters.append(
                f"[{current}][{labels[i]}]acrossfade=d={crossfade_s:.3f}:"
                f"c1=qsin:c2=qsin[{out}]"
            )
            current = out
        # The rotation boundary is baked in: this stream ends at play_for_s and
        # the server's next pick starts a fresh stream, so fading the head and
        # tail here IS the node's track-change fade (runtime volume ramps are
        # off the table — the entity volume is shared with the cue pipeline).
        fade = (f",afade=t=in:st=0:d={fade_s:.3f}"
                f",afade=t=out:st={play_for_s - fade_s:.3f}:d={fade_s:.3f}"
                if fade_s else "")
        filters.append(f"[{current}]atrim=0:{play_for_s:.3f},asetpts=N/SR/TB,"
                       f"volume={gain:.3f}{fade}[out]")
        tmp_path = out_path + ".tmp"
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            *inputs,
            "-filter_complex", ";".join(filters),
            "-map", "[out]",
            "-f", "mp3",
            "-codec:a", "libmp3lame",
            "-q:a", "4",
            tmp_path,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
            os.replace(tmp_path, out_path)
            logger.info(f"Prepared node ambience loop {rel_name} from {file_name} "
                        f"({copies}x, {crossfade_s:.2f}s crossfade)")
            return rel_name
        except (OSError, subprocess.SubprocessError) as e:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except OSError:
                pass
            stderr = getattr(e, "stderr", "") or str(e)
            logger.warning(f"Could not prepare node ambience loop for {file_name}: {stderr}")
            return None

    def prepare_node_ambience_stream(self, effect_name, file_name, playback, gain=1.0):
        """Return a node-friendly ambience asset for ESPHome speaker playback.

        Short loopable browser beds become longer crossfaded mono MP3s. Long
        one-shot beds are still normalized to mono 44.1 kHz MP3 so the ESP's
        mono media pipeline never has to decode a stereo source. Either way
        `gain` (the pool volume) is baked in — see prepare_node_ambience_loop.
        """
        loop_file = self.prepare_node_ambience_loop(effect_name, file_name, playback, gain)
        if loop_file:
            return loop_file

        policy = self._node_policy(effect_name)
        if not policy.get("node_prepare_stream", True):
            return None
        # Track-change fade for once-played beds: head fade always, tail fade
        # only when the decoded duration says where the tail is.
        try:
            duration_s = float(playback.get("duration_s") or 0)
        except (TypeError, ValueError):
            duration_s = 0.0
        cap_s = duration_s / 3.0 if duration_s > 0 else float("inf")
        fade_s = self._stream_fade_s(playback, policy, cap_s)
        fade = f",afade=t=in:st=0:d={fade_s:.3f}" if fade_s else ""
        if fade_s and duration_s > 0:
            fade += f",afade=t=out:st={duration_s - fade_s:.3f}:d={fade_s:.3f}"
        source_path, rel_name = self._generated_node_stream_name(
            file_name, gain, fade_desc=f"-fade{fade_s:.3f}" if fade_s else "")
        if not source_path or not rel_name:
            return None
        out_path = os.path.join(self.base_dir, "audio_files", rel_name)
        if os.path.exists(out_path):
            return rel_name
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        tmp_path = out_path + ".tmp"
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", source_path,
            "-af", f"aformat=channel_layouts=mono,aresample=44100,volume={gain:.3f}{fade}",
            "-f", "mp3",
            "-codec:a", "libmp3lame",
            "-q:a", "4",
            tmp_path,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=60)
            os.replace(tmp_path, out_path)
            logger.info(f"Prepared node ambience stream {rel_name} from {file_name}")
            return rel_name
        except (OSError, subprocess.SubprocessError) as e:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except OSError:
                pass
            stderr = getattr(e, "stderr", "") or str(e)
            logger.warning(f"Could not prepare node ambience stream for {file_name}: {stderr}")
            return None

    def warm_node_streams(self, effect_names):
        """Pre-generate the gain-baked node streams for every file in the
        given pools. BLOCKING (one ffmpeg transcode per uncached file — 30-60s
        for a 15-minute bed track on the Pi): run via asyncio.to_thread from a
        background task. Keeps bed rotations cache-hit, so a rotation never
        has to transcode at pick time (2026-08-17: a cold rotation inline on
        the event loop froze the whole server for 49s and ate VMM's button
        POSTs; the payload build is threaded now, and this warmup keeps even
        the threaded path instant)."""
        prepared = 0
        for effect_name in effect_names:
            config = self.get_audio_config(effect_name)
            if not config.get('audio_files'):
                continue
            volume = config.get('volume', self.audio_config.get('default_volume', 0.7))
            for file_name in config.get('audio_files', []):
                playback = self.ambience_playback(effect_name, file_name)
                if self.prepare_node_ambience_stream(effect_name, file_name,
                                                     playback, gain=volume):
                    prepared += 1
        return prepared

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

        try:
            fade_s = max(0.0, float(policy.get('fade_s', 0.0)))
        except (TypeError, ValueError):
            fade_s = 0.0

        return {
            'loop': loop,
            'duration_s': round(duration, 3) if duration is not None else None,
            'play_for_s': max(1.0, round(play_for, 3)),
            'fade_s': round(fade_s, 3),
        }
