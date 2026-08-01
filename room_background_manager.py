"""Always-on per-room background sound (Tim, 2026-08-01).

Rooms opted in through audio_config.json's top-level `room_backgrounds` map
(room name -> an effects entry, usually the room's -Background pool) get one
random pick from that pool LOOPING on the room's ambience channel whenever
anything can play audio there. This is a different feature from maze-wide
background music (/api/start_music, the `music/` directory): that one is a
single rotating track broadcast to every speaker, this one is a room keeping
its own sound. The two meet in the clients: a room with an active background
bed mutes the maze-wide music on its speaker instead of mixing with it, and
the music comes back when the bed stops (client/audio_manager.py zones,
node_audio_manager.py nodes). Music mode on or off never touches these —
they are on whenever the room has a working speaker.

A reconcile loop (TICK_S) starts beds as clients appear; a room's bed is
marked lost when the last client covering it disconnects, so the next tick
restarts it for whoever reconnects. Stop-alls deliberately do NOT reach in
here — "always on" means a maze-wide silence lasts one tick for these rooms.

Cuddle Cross never belongs in `room_backgrounds`: its bed follows the floor
projection theme and is owned by floor_show_manager.py. The reconciler
refuses the floor-show room outright rather than fighting over the channel.

Runtime opt-in/out for auditioning (not persisted — edit audio_config.json,
or use the audio console, to keep one): POST /api/room_backgrounds
{"room": ..., "effect": ...|null}.
"""
import asyncio
import logging

logger = logging.getLogger(__name__)

TICK_S = 10.0


class RoomBackgroundManager:
    def __init__(self, audio_manager, remote_host_manager, reserved_room=None):
        self.audio_manager = audio_manager
        self.remote_host_manager = remote_host_manager
        self.reserved_room = reserved_room  # the floor show's room
        self.pools = {}    # room -> effects entry name (the wanted state)
        self.playing = {}  # room -> file started (what we believe is looping)
        self._task = None
        self._load()

    def _load(self):
        config = self.audio_manager.audio_config.get('room_backgrounds') or {}
        for room, effect in config.items():
            if room.startswith('_'):
                continue  # _comment keys
            self.set_room(room, effect, source='audio_config.json')

    def set_room(self, room, effect, source='api'):
        """Opt a room in (effect name) or out (None). Returns (ok, message)."""
        if self.reserved_room and room.lower() == self.reserved_room.lower():
            return False, (f"{room} is the floor show's room — its background "
                           "follows the projection theme (floor_show_manager)")
        if effect is None:
            self.pools.pop(room, None)
            return True, f"{room} opted out of a room background"
        entry = self.audio_manager.audio_config['effects'].get(effect)
        if entry is None:
            logger.warning(f"room_backgrounds ({source}): {room} -> {effect!r} "
                           "is not an effects entry; skipped")
            return False, f"no effects entry named {effect!r}"
        if not entry.get('audio_files'):
            logger.warning(f"room_backgrounds ({source}): {room} -> {effect} "
                           "has an empty pool; skipped")
            return False, f"{effect} has no audio files"
        self.pools[room] = effect
        logger.info(f"Room background ({source}): {room} -> {effect}")
        return True, f"{room} background is {effect}"

    def state(self):
        return {
            'configured': dict(self.pools),
            'playing': dict(self.playing),
        }

    def bed_for_room(self, room):
        """The pool a just-registered client should be looping for `room`, or
        None — remote_host_manager asks on every client register (same rejoin
        contract as the floor show's bed_for_room)."""
        for known, effect in self.pools.items():
            if known.lower() == room.lower() and known in self.playing:
                return effect
        return None

    def client_gone(self, rooms):
        """A client disconnected. Any of its rooms left with NO other audio
        client gets its bed marked not-playing, so the reconciler restarts it
        when something reconnects."""
        for room in rooms or []:
            for known in list(self.playing):
                if known.lower() != room.lower():
                    continue
                if not self.remote_host_manager.has_audio_client(known):
                    del self.playing[known]
                    logger.info(f"Room background in {known} lost its last "
                                "client; will restart on reconnect")

    def ensure_running(self):
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())
        return self._task

    async def apply_now(self):
        """One immediate reconcile (the POST route) instead of waiting a tick."""
        await self._reconcile()

    async def _run(self):
        logger.info(f"Room background reconciler up "
                    f"({len(self.pools)} room(s) configured)")
        while True:
            try:
                await self._reconcile()
            except Exception as e:
                logger.error(f"Room background reconcile failed: {e}", exc_info=True)
            await asyncio.sleep(TICK_S)

    async def _reconcile(self):
        for room in list(self.playing):
            if room not in self.pools:  # opted out at runtime
                await self.remote_host_manager.stop_room_ambience(room)
                del self.playing[room]
                logger.info(f"Room background stopped in {room}")
        for room, effect in self.pools.items():
            if room in self.playing:
                continue
            if not self.remote_host_manager.has_audio_client(room):
                continue  # nothing to play it yet; next tick tries again
            started = await self.remote_host_manager.start_room_ambience(room, effect)
            if started:
                self.playing[room] = started
                logger.info(f"Room background '{effect}' looping in {room} ({started})")
