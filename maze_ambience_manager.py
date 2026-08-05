"""Always-on maze-wide ambience bed.

This replaces the old maze-wide global-track mode. The bed is just
another configured effects pool (`audio_config.json` top-level
`maze_ambience` -> effects entry), played on a dedicated maze ambience channel
across every speaker that can play audio.

Room beds have priority on their own speaker/zone. Effects and ambient
one-shots mix over whichever bed is active.
"""
import asyncio
import logging
import time

logger = logging.getLogger(__name__)

TICK_S = 10.0


class MazeAmbienceManager:
    def __init__(self, audio_manager, remote_host_manager):
        self.audio_manager = audio_manager
        self.remote_host_manager = remote_host_manager
        self.effect = None
        self.default_effect = None
        self.playing = None
        self.loop = None
        self.duration_s = None
        self.play_for_s = None
        self.started_at = None
        self._task = None
        self._load()

    def _load(self):
        effect = self.audio_manager.audio_config.get('maze_ambience')
        if isinstance(effect, dict):
            effect = effect.get('effect')
        self.default_effect = effect
        self.set_effect(effect, source='audio_config.json')

    def set_effect(self, effect, source='api'):
        """Opt the maze-wide ambience bed in or out. Returns (ok, message)."""
        if effect is None:
            self.effect = None
            return True, "maze ambience opted out"
        entry = self.audio_manager.audio_config['effects'].get(effect)
        if entry is None:
            logger.warning(f"maze_ambience ({source}): {effect!r} is not an effects entry; skipped")
            return False, f"no effects entry named {effect!r}"
        if not entry.get('audio_files'):
            logger.warning(f"maze_ambience ({source}): {effect} has an empty pool; skipped")
            return False, f"{effect} has no audio files"
        self.effect = effect
        logger.info(f"Maze ambience ({source}): {effect}")
        return True, f"maze ambience is {effect}"

    def state(self):
        return {
            'configured': self.effect,
            'playing': self.playing,
            'loop': self.loop,
            'duration_s': self.duration_s,
            'play_for_s': self.play_for_s,
            'elapsed_s': (
                round(time.monotonic() - self.started_at, 3)
                if self.started_at is not None else None
            ),
        }

    def bed(self):
        """The effect a just-registered client should be looping, or None."""
        return (
            (self.effect, self.playing, self.started_at)
            if self.effect and self.playing else None
        )

    def ensure_running(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())
        return self._task

    async def apply_now(self, force=False):
        await self._reconcile(force=force)

    async def _run(self):
        logger.info(f"Maze ambience reconciler up ({self.effect or 'none'} configured)")
        while True:
            try:
                await self._reconcile()
            except Exception as e:
                logger.error(f"Maze ambience reconcile failed: {e}", exc_info=True)
            await asyncio.sleep(TICK_S)

    async def _reconcile(self, force=False):
        if self.playing and not self.effect:
            await self.remote_host_manager.stop_maze_ambience()
            self._clear_playing()
            logger.info("Maze ambience stopped")
            return
        if not self.effect:
            return
        if self.playing:
            expired = (
                self.started_at is not None
                and self.play_for_s is not None
                and time.monotonic() - self.started_at >= self.play_for_s
            )
            if not force and not expired:
                await self.remote_host_manager.retry_node_maze_ambience()
                return
            if force:
                logger.info("Maze ambience forced to a fresh pick")
            else:
                logger.info(f"Maze ambience rotating after {self.play_for_s:.1f}s")
        if not self.remote_host_manager.audio_rooms():
            return
        started = await self.remote_host_manager.start_maze_ambience(self.effect)
        if started:
            self._set_playing(started)
            mode = 'looping' if self.loop else 'once'
            logger.info(f"Maze ambience '{self.effect}' {mode} ({self.playing}) "
                        f"for {self.play_for_s:.1f}s")

    def _set_playing(self, payload):
        self.playing = payload['file_name']
        self.loop = payload.get('loop')
        self.duration_s = payload.get('duration_s')
        self.play_for_s = payload.get('play_for_s')
        self.started_at = payload.get('sync_started_at_s') or time.monotonic()

    def _clear_playing(self):
        self.playing = None
        self.loop = None
        self.duration_s = None
        self.play_for_s = None
        self.started_at = None
