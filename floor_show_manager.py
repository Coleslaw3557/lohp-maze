"""Cuddle Cross follows the floor projection — bed audio, accents, light colour.

The floor show renders in its own process (projection_renderer.py on the Pi,
sim_ui's engine on the bench) and owns the story on the deck. This module is
the server's half of that story, for the one room the projector lights:

  * the CURRENT floor theme (lava / jungle / temple / water / chamber), which
    also picks the room's light palette — effects_manager.set_floor_theme()
    recolours the entry swell and the maze theme's ambient wash for the room
  * a looping ambience BED under the room for as long as the show is up
    (LAVA: Tim's lava.wav 2026-07-30, JUNGLE: junglenight.wav, TEMPLE: the
    altar torch's brazier crackle, WATER: drips — both 2026-08-01).
    Beds ride their own audio channel, so an effect taking the room over
    never cuts them and accents mix on top
  * AMBIENT one-shots at random intervals while the show is up (Tim,
    2026-08-01) — audio only, no lights: birdsong over the jungle bed, wind
    and ravens for the temple. Each theme sets its own interval range; the
    file comes from the theme's ambient pool with the usual anti-repeat
  * occasional ACCENT hits fired by the engine's own events — a stone going
    under a walker, Kukulkan surfacing. Each accent is a real room effect: a
    capped ember flare on the two pars plus one file from the theme's accent
    pool, picked by the usual anti-repeat pool logic.

The renderer POSTs /api/floor_event every couple of seconds and whenever
events happen. `active` in that payload is the authority for the bed and the
ambient timer, so a renderer that dies or a show that times out just goes
quiet (WATCHDOG_S) instead of leaving the deck rumbling to an empty room.

All five themes have sounds today (CHAMBER landed last, 2026-08-01: a
mysterious-perc bed and the trap doors' merged MGS hit). A theme with no
`bed`/`ambient`/`accents` entry is still a supported state, not a broken one.
"""
import asyncio
import logging
import os
import random
import time

from effects.cuddle_puddle import THEME_PALETTES

logger = logging.getLogger(__name__)

ROOM = "Cuddle Cross"
# The floor themes this room knows how to dress (projection_engine.THEMES).
# Kept as the light palettes' key set rather than importing the engine: the
# server has no reason to pull numpy in, and a theme with no palette is one
# this room could not follow anyway.
KNOWN_THEMES = frozenset(THEME_PALETTES)

# Per floor theme: the looping bed pool, an `ambient` pool fired on its own
# random timer (audio only — uniform delay in [min_s, max_s] between shots),
# plus the engine events that earn an accent. For accents: `p` = chance of
# firing, `cooldown` = seconds since the last accent from the SAME effect (so
# a pop only speaks up in a genuinely quiet stretch, while a breach can still
# land right after its own approach swell), `rank` = which event wins when a
# batch carries several. Event names come from projection_engine.py's _emit
# calls.
THEME_SHOWS = {
    'lava': {
        'bed': 'Cuddle-Lava-Bed',
        # sparse: the engine events already voice the deck when people move
        'ambient': {'effect': 'Cuddle-Lava-Ambient', 'min_s': 20.0, 'max_s': 50.0},
        'accents': {
            # Kukulkan: the approach under the crust, then the head breaking out
            'monster_breach': {'effect': 'Cuddle-Lava-Breach', 'p': 1.0, 'cooldown': 3.0, 'rank': 50},
            'monster_swim': {'effect': 'Cuddle-Lava-Breach', 'p': 0.9, 'cooldown': 3.0, 'rank': 40},
            # a stepping stone going under someone, and the replacement surfacing
            'sink': {'effect': 'Cuddle-Lava-Hit', 'p': 0.75, 'cooldown': 11.0, 'rank': 30},
            'rise': {'effect': 'Cuddle-Lava-Hit', 'p': 0.35, 'cooldown': 11.0, 'rank': 20},
            # bubbles burst constantly (~0.6 Hz) — rare and heavily spaced, or
            # the room turns into a drum machine
            'pop': {'effect': 'Cuddle-Lava-Hit', 'p': 0.05, 'cooldown': 24.0, 'rank': 10},
        },
    },
    'jungle': {
        'bed': 'Cuddle-Jungle-Bed',
        # lively canopy: mostly birdsong (16 of the 24 files), the odd beast
        'ambient': {'effect': 'Cuddle-Jungle-Ambient', 'min_s': 7.0, 'max_s': 22.0},
    },
    'temple': {
        # the altar torch: Tim's "projection with the torch" (2026-08-01)
        'bed': 'Cuddle-Temple-Bed',
        'ambient': {'effect': 'Cuddle-Temple-Ambient', 'min_s': 10.0, 'max_s': 35.0},
    },
    'water': {
        'bed': 'Cuddle-Water-Bed',
        # sparse like lava: drips changing pattern, a winter wind through the ford
        'ambient': {'effect': 'Cuddle-Water-Ambient', 'min_s': 12.0, 'max_s': 35.0},
    },
    'chamber': {
        # one of the sixteen mysterious percs per bed start (Tim 2026-08-01)
        'bed': 'Cuddle-Chamber-Bed',
        'accents': {
            # a trap door taking someone's step — linger-open or sprint-slam
            # both emit trap_open; 2s cooldown so two doors close together
            # don't double-hit
            'trap_open': {'effect': 'Cuddle-Chamber-Trap', 'p': 1.0, 'cooldown': 2.0, 'rank': 50},
        },
    },
}

WATCHDOG_S = 20.0      # no report for this long: renderer gone, stop the bed
WATCHDOG_TICK_S = 5.0


def read_saved_theme(repo_dir):
    """The theme the projector was last showing. Both renderers persist it —
    projection_renderer.py to .floor_theme, the sim to sim/.floor_theme — so
    the room's lights are already the right colour before the first report."""
    for path in (os.path.join(repo_dir, '.floor_theme'),
                 os.path.join(repo_dir, 'sim', '.floor_theme')):
        try:
            with open(path) as f:
                name = f.read().strip()
        except OSError:
            continue
        if name:
            return name
    return None


class FloorShowManager:
    def __init__(self, effects_manager, remote_host_manager, room=ROOM, rng=None):
        self.effects_manager = effects_manager
        self.remote_host_manager = remote_host_manager
        self.room = room
        self.theme = None
        self.active = False
        self.bed = None            # ambience pool currently playing, or None
        self.ambient = None        # ambient one-shot pool currently armed, or None
        self.last_report = 0.0     # monotonic; 0 = the renderer has never reported
        self._last_fire = {}       # accent effect name -> monotonic
        self._rng = rng or random.SystemRandom()
        self._lock = asyncio.Lock()
        self._watchdog = None
        self._ambient_task = None

    # --- state ---

    def state(self):
        return {
            'room': self.room,
            'theme': self.theme,
            'active': self.active,
            'bed': self.bed,
            'ambient': self.ambient,
            'has_sounds': self.theme in THEME_SHOWS,
            'age_s': (round(time.monotonic() - self.last_report, 1)
                      if self.last_report else None),
        }

    def prime_theme(self, theme):
        """Colour the room for a theme without touching audio — used at startup
        (the show is not running yet) and safe to call before the event loop."""
        self._adopt_theme(theme)

    def _adopt_theme(self, theme):
        """Take a theme name from a renderer. Anything this room has no palette
        for is ignored rather than silently repainting it."""
        if not theme or theme == self.theme:
            return False
        if theme not in KNOWN_THEMES:
            logger.warning(f"Floor renderer reported unknown theme {theme!r}; "
                           f"{self.room} stays on {self.theme!r} "
                           f"(known: {sorted(KNOWN_THEMES)})")
            return False
        self.theme = theme
        self.effects_manager.set_floor_theme(theme)
        return True

    # --- inputs ---

    async def handle_report(self, theme=None, active=None, events=None):
        """One report from the floor renderer: POST /api/floor_event.
        Returns the accent effect fired for this batch, or None."""
        async with self._lock:
            self.last_report = time.monotonic()
            self._ensure_watchdog()
            if self._adopt_theme(theme):
                logger.info(f"Floor show theme -> {theme}")
            if active is not None:
                self.active = bool(active)
            await self._reconcile_bed()
            self._reconcile_ambient()
            accent = self._pick_accent(events or [])
        if accent:
            asyncio.create_task(self._run_accent(*accent))
            return accent[0]
        return None

    async def set_theme(self, theme):
        """A theme switch that reached us before the renderer's next report
        (the orb / the sim's Floor button, through /api/next_floor_theme)."""
        async with self._lock:
            if not self._adopt_theme(theme):
                return False
            await self._reconcile_bed()
            self._reconcile_ambient()
        logger.info(f"Floor show theme -> {theme} (relayed)")
        return True

    async def stop(self):
        """Silence the room's bed and ambient timer (a maze-wide stop, or
        shutdown). The next report from a running show starts them again — the
        projector is the authority on whether the deck has a show on it."""
        async with self._lock:
            self.active = False
            await self._reconcile_bed()
            self._reconcile_ambient()

    # --- internals ---

    async def _reconcile_bed(self):
        """Caller holds the lock. One place decides what should be playing."""
        show = THEME_SHOWS.get(self.theme) or {}
        want = show.get('bed') if self.active else None
        if want == self.bed:
            return
        if want is None:
            await self.remote_host_manager.stop_room_ambience(self.room)
            logger.info(f"Floor bed stopped in {self.room}")
            self.bed = None
            return
        # With nothing to play it (unit down, node not built yet) there is no
        # point failing loudly on every report all night — the next one tries
        # again, so a client that reconnects gets its bed immediately.
        if not self.remote_host_manager.has_audio_client(self.room):
            return
        # A theme swap replaces the running bed: the client's ambience channel
        # is per room, so starting the new one ends the old one.
        started = await self.remote_host_manager.start_room_ambience(self.room, want)
        self.bed = want if started else None
        if started:
            logger.info(f"Floor bed '{want}' looping in {self.room} ({started})")

    def bed_for_room(self, room):
        """The bed a just-registered audio client should be playing for `room`,
        or None. remote_host_manager asks on every client register, so a
        reloaded sim tab (or a rebooted unit) rejoins a live show's bed instead
        of staying silent until the next theme change."""
        return self.bed if room == self.room else None

    def _reconcile_ambient(self):
        """Caller holds the lock. Arms/refreshes/cancels the random-interval
        ambient one-shot timer to match the active theme. Unlike the bed there
        is nothing to stop on a client — each shot is a one-and-done file — so
        this only manages the server-side timer task."""
        show = THEME_SHOWS.get(self.theme) or {}
        rule = show.get('ambient') if self.active else None
        want = rule['effect'] if rule else None
        if want == self.ambient:
            return
        task, self._ambient_task = self._ambient_task, None
        if task is not None:
            task.cancel()
        self.ambient = want
        if rule:
            self._ambient_task = asyncio.create_task(self._ambient_loop(rule))
            logger.info(f"Floor ambient pool '{want}' armed in {self.room} "
                        f"(every {rule['min_s']:.0f}-{rule['max_s']:.0f}s)")

    async def _ambient_loop(self, rule):
        """One theme's ambient timer: sleep a random stretch, fire one file
        from the pool (audio only — no lights), repeat. The pool's volume and
        anti-repeat selection come from audio_config via play_effect_audio."""
        effect = rule['effect']
        try:
            while True:
                await asyncio.sleep(self._rng.uniform(rule['min_s'], rule['max_s']))
                async with self._lock:
                    if not self.active or self.ambient != effect:
                        return
                    # Nobody to play it (unit down, node not built): skip this
                    # beat quietly, exactly like the bed does, and try again
                    # after the next interval.
                    if not self.remote_host_manager.has_audio_client(self.room):
                        continue
                ok = await self.remote_host_manager.play_effect_audio(
                    effect, rooms=[self.room])
                if ok:
                    logger.info(f"Floor ambient {effect} in {self.room}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Floor ambient loop for {effect} died: {e}", exc_info=True)

    def _pick_accent(self, events):
        """Caller holds the lock. At most ONE accent per batch: the highest
        ranked event that passes its own dice roll and cooldown."""
        if not self.active:
            return None
        accents = (THEME_SHOWS.get(self.theme) or {}).get('accents') or {}
        candidates = [(accents[ev['e']], ev) for ev in events
                      if isinstance(ev, dict) and ev.get('e') in accents]
        if not candidates:
            return None
        now = time.monotonic()
        for rule, event in sorted(candidates, key=lambda c: -c[0]['rank']):
            effect = rule['effect']
            if now - self._last_fire.get(effect, -1e9) < rule['cooldown']:
                continue
            if self._rng.random() > rule['p']:
                continue
            self._last_fire[effect] = now
            return effect, event.get('e')
        return None

    async def _run_accent(self, effect_name, event_name):
        try:
            success, message = await self.effects_manager.apply_effect_to_room(
                self.room, effect_name)
            if success:
                logger.info(f"Floor accent {effect_name} on '{event_name}' in {self.room}")
            else:
                logger.warning(f"Floor accent {effect_name} failed: {message}")
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Error running floor accent {effect_name}: {e}", exc_info=True)

    def _ensure_watchdog(self):
        if self._watchdog is None or self._watchdog.done():
            self._watchdog = asyncio.create_task(self._watch())

    async def _watch(self):
        """Stop the bed if the renderer stops reporting. A live show always
        reports (heartbeat every couple of seconds), so silence means the
        renderer died, was restarted, or lost the network — none of which
        should leave a room rumbling on its own."""
        while True:
            await asyncio.sleep(WATCHDOG_TICK_S)
            async with self._lock:
                if self.bed is None and self.ambient is None and not self.active:
                    return
                if time.monotonic() - self.last_report > WATCHDOG_S:
                    logger.warning(f"No floor report for {WATCHDOG_S:.0f}s — "
                                   f"stopping the bed in {self.room}")
                    self.active = False
                    await self._reconcile_bed()
                    self._reconcile_ambient()
                    return
