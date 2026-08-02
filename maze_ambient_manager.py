"""Roaming ambient one-shots outside the floor show (Tim, 2026-08-01).

Configured in audio_config.json under top-level `ambient_oneshots`; both
flavours are audio-only (no lights) and pick files through the usual
anti-repeat pool logic (play_effect_audio):

  * `rooms`: room name -> {effect, min_s, max_s}. That room runs its own
    timer and fires one file from its pool in that room — the Entrance's
    hallow murmurs over its hallowloop bed.
  * `maze`: {effect, min_s, max_s}. ONE maze-wide timer; each firing picks a
    random room that can play audio RIGHT NOW (remote_host_manager
    .audio_rooms) and lands one file from the shared pool there — a crow at
    the Gate, a wolf somewhere past Porto. The next firing rolls a new room.

This is the texture layer between effects: quieter than entry cues, mixing
over room beds and the maze-wide ambience bed alike. Stop-alls don't reach in
here — each shot is one-and-done, so a maze-wide stop only silences what is
already in the air.

The floor-show room (Cuddle Cross) is excluded from both flavours: its
ambience follows the projection theme (floor_show_manager.py THEME_SHOWS),
and two random engines talking over each other is mud, not depth.

A room with no audio client skips its beat quietly and tries again next
interval (same contract as the floor show's ambient loop), so units coming
and going never kill a timer.

Audition without waiting out an interval (main.py): POST /api/ambient
{"maze": true} or {"room": "Entrance"}; GET /api/ambient reports what's
armed.
"""
import asyncio
import logging
import random

logger = logging.getLogger(__name__)


class MazeAmbientManager:
    def __init__(self, audio_manager, remote_host_manager, reserved_room=None,
                 rng=None):
        self.audio_manager = audio_manager
        self.remote_host_manager = remote_host_manager
        self.reserved_room = reserved_room  # the floor show's room
        self._rng = rng or random.SystemRandom()
        self.maze_rule = None    # {'effect', 'min_s', 'max_s'} or None
        self.room_rules = {}     # room name -> rule dict
        self._tasks = []
        self._load()

    # --- config ---

    def _load(self):
        config = self.audio_manager.audio_config.get('ambient_oneshots') or {}
        maze = config.get('maze')
        if maze is not None and self._usable(maze, 'maze'):
            self.maze_rule = maze
        for room, rule in (config.get('rooms') or {}).items():
            if room.startswith('_'):
                continue  # _comment keys
            if self.reserved_room and room.lower() == self.reserved_room.lower():
                logger.warning(f"ambient_oneshots: {room} is the floor show's "
                               "room — its ambience follows the projection "
                               "theme (floor_show_manager); skipped")
                continue
            if self._usable(rule, room):
                self.room_rules[room] = rule

    def _usable(self, rule, label):
        """One bad entry gets logged and dropped; the rest keep running."""
        effect = rule.get('effect') if isinstance(rule, dict) else None
        entry = self.audio_manager.audio_config['effects'].get(effect or '')
        if entry is None:
            logger.warning(f"ambient_oneshots ({label}): {effect!r} is not an "
                           "effects entry; skipped")
            return False
        if not entry.get('audio_files'):
            logger.warning(f"ambient_oneshots ({label}): {effect} has an "
                           "empty pool; skipped")
            return False
        try:
            lo, hi = float(rule['min_s']), float(rule['max_s'])
        except (KeyError, TypeError, ValueError):
            lo = hi = 0.0
        if not 0 < lo <= hi:
            logger.warning(f"ambient_oneshots ({label}): needs 0 < min_s <= "
                           f"max_s, got {rule.get('min_s')!r}/"
                           f"{rule.get('max_s')!r}; skipped")
            return False
        return True

    def state(self):
        return {
            'maze': dict(self.maze_rule) if self.maze_rule else None,
            'rooms': {room: dict(rule) for room, rule in self.room_rules.items()},
        }

    # --- runtime ---

    def ensure_running(self):
        """Arm every configured timer. Idempotent: timers live for the
        server's whole life, so there is nothing to reconcile later."""
        if self._tasks:
            return
        if self.maze_rule:
            self._tasks.append(asyncio.create_task(self._maze_loop(self.maze_rule)))
        for room, rule in self.room_rules.items():
            self._tasks.append(asyncio.create_task(self._room_loop(room, rule)))
        if self._tasks:
            logger.info(f"Ambient one-shots up: "
                        f"maze pool {'armed' if self.maze_rule else 'none'}, "
                        f"{len(self.room_rules)} room pool(s)")

    async def _room_loop(self, room, rule):
        try:
            while True:
                await asyncio.sleep(self._rng.uniform(rule['min_s'], rule['max_s']))
                await self._fire_room(room, rule['effect'])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Ambient loop for {room} died: {e}", exc_info=True)

    async def _maze_loop(self, rule):
        try:
            while True:
                await asyncio.sleep(self._rng.uniform(rule['min_s'], rule['max_s']))
                await self._fire_maze(rule['effect'])
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Maze ambient loop died: {e}", exc_info=True)

    async def _fire_room(self, room, effect):
        """One shot in one room. A room nothing can play right now is a quiet
        skip (the next interval tries again), not an error worth logging."""
        if not self.remote_host_manager.has_audio_client(room):
            return False, f"nothing can play audio in {room} right now"
        ok = await self.remote_host_manager.play_effect_audio(effect, rooms=[room])
        if ok:
            logger.info(f"Ambient {effect} in {room}")
            return True, f"{effect} fired in {room}"
        return False, f"{effect} failed in {room}"

    async def _fire_maze(self, effect):
        rooms = self._eligible_rooms()
        if not rooms:
            return False, "no room can play audio right now"
        return await self._fire_room(self._rng.choice(rooms), effect)

    def _eligible_rooms(self):
        reserved = (self.reserved_room or '').lower()
        return [room for room in self.remote_host_manager.audio_rooms()
                if room.lower() != reserved]

    async def fire_now(self, room=None, maze=False):
        """One immediate shot for auditioning (POST /api/ambient).
        Returns (ok, message)."""
        if maze:
            if not self.maze_rule:
                return False, "no maze ambient pool configured"
            return await self._fire_maze(self.maze_rule['effect'])
        if room:
            for known, rule in self.room_rules.items():
                if known.lower() == room.lower():
                    return await self._fire_room(known, rule['effect'])
            return False, (f"{room} has no ambient pool "
                           "(audio_config ambient_oneshots.rooms)")
        return False, 'pass {"maze": true} or {"room": <name>}'
