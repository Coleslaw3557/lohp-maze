import colorsys
import logging
import math
import time
import threading
import asyncio
from effect_utils import (generate_theme_values, snap_hue_out_of_yellow,
                          YELLOW_ARC, YELLOW_SPLIT)

logger = logging.getLogger(__name__)

# Every room's ambient lens over the maze theme (Tim's lighting pass,
# 2026-08-01): the theme drives the MOTION, the profile decides how each room
# wears it — a brightness ceiling (`cap`), a pull toward the room's own colour
# (`rgb` + `mix`; 1.0 would ignore the theme's hue entirely), a personal
# tempo (`rate` scales the theme clock: 0.6 = slow forest sway, 1.4 = the
# chase-track room fidgets), and NO WHITE ever (profiles force w=0 — bright
# white/yellow is reserved for effects that truly need it: camera flashes and
# lightning).
#
# Colours follow each room's own SOUND (see audio_config room_backgrounds /
# entry pools): Entrance breathes hallowloop violet, Guy Line sways to the
# forest wind, Deep Playa fidgets to the chase track, and so on.
#
# Cuddle Cross is the projection room: floor_show_manager ->
# effects_manager.set_floor_theme() REPLACES its rgb/cap live as the floor
# show changes theme; the entry here is only the boot value until the
# renderer first reports. Camp Sign is deliberately absent — the sign wears
# its own bridge-side looks, not the maze wash.
ROOM_LIGHT_PROFILES = {
    "Cuddle Cross": {"cap": 48, "rgb": (255, 60, 110), "mix": 0.75},
    "Entrance": {"cap": 170, "rgb": (105, 35, 190), "mix": 0.32, "rate": 0.65},
    "Gate": {"cap": 165, "rgb": (225, 70, 10), "mix": 0.32, "rate": 0.72},
    "Cop Dodge": {"cap": 175, "rgb": (35, 75, 230), "mix": 0.34, "rate": 0.95},
    "Photo Bomb Room": {"cap": 170, "rgb": (235, 35, 155), "mix": 0.32, "rate": 0.85},
    "Porto Room": {"cap": 155, "rgb": (45, 195, 65), "mix": 0.35, "rate": 0.62},
    "Bike Lock Room": {"cap": 165, "rgb": (210, 65, 20), "mix": 0.34, "rate": 0.78},
    "Guy Line Climb": {"cap": 150, "rgb": (25, 165, 85), "mix": 0.36, "rate": 0.55},
    "Monkey Room": {"cap": 170, "rgb": (175, 45, 220), "mix": 0.33, "rate": 0.92},
    "No Friends Monday": {"cap": 175, "rgb": (235, 50, 115), "mix": 0.3, "rate": 0.86},
    "Sparkle Pony Room": {"cap": 170, "rgb": (235, 60, 190), "mix": 0.32, "rate": 0.8},
    "Vertical Moop March": {"cap": 160, "rgb": (70, 195, 65), "mix": 0.34, "rate": 0.7},
    "Deep Playa Handshake": {"cap": 175, "rgb": (185, 35, 235), "mix": 0.32, "rate": 1.0},
    "Temple Room": {"cap": 155, "rgb": (35, 145, 130), "mix": 0.36, "rate": 0.58},
    "Exit": {"cap": 175, "rgb": (55, 215, 85), "mix": 0.3, "rate": 0.8},
}

# Attract mode: with nobody driving, the maze runs these slow dark looks on
# its own and rolls to the next every ATTRACT_DWELL_S.
# A manual /api/set_theme keeps rotation alive but restarts the dwell clock —
# the maze never gets stuck on one look because someone tapped the orb.
ATTRACT_THEMES = ["DeepCanopy", "EmberUndercroft", "CenoteDrift",
                  "UltravioletVines", "MoonlitStone", "RitualAurora"]
ATTRACT_DWELL_S = 7 * 60
ATTRACT_TICK_S = 20
# After a deliberate stop the maze stays dark this long, then attract
# relights it — long enough that a stop reads as intentional (and stays out
# of test windows), short enough that the maze never sits dark all night.
ATTRACT_RELIGHT_S = 180

# While a radar room is OCCUPIED (entry fired, vacate not yet), its profile
# mix is pinned here: the room locks onto its own colour instead of tinting
# the wandering theme hue. The theme still drives brightness/motion, so the
# held look breathes slowly and stays inside the cap and palette clamps.
# Vacate un-pins it and the room rejoins the plain theme blend.
OCCUPIED_MIX = 0.85

# Rooms that swap the theme for their OWN look while occupied, instead of the
# OCCUPIED_MIX blend (Tim 2026-08-17, VMM: no flashing on entry — a
# medium-paced green/blue/red cycle while anyone is inside). The hue
# ping-pongs hue_lo -> hue_hi and back (green -> blue -> red for VMM), which
# never crosses the forbidden yellow arc; period_s is the full round trip and
# each successive fixture trails by fixture_phase_s so a two-par room reads
# as a moving gradient rather than one flat colour. Painted at the theme tick
# rate; a press-flash interrupt owns its fixtures and the gradient resumes
# around it. The win hold outranks the gradient.
ROOM_OCCUPIED_GRADIENTS = {
    "Vertical Moop March": {
        "hue_lo": 1.0 / 3.0,   # green
        "hue_hi": 1.0,         # red, passing blue at the midpoint
        "period_s": 12.0,      # medium pace: full green->red->green round trip
        "total": 160,          # the room's ambient cap
        "fixture_phase_s": 1.8,
    },
}


class ThemeManager:
    def __init__(self, dmx_state_manager, light_config_manager, interrupt_handler):
        self.dmx_state_manager = dmx_state_manager
        self.light_config_manager = light_config_manager
        self.interrupt_handler = interrupt_handler
        self.themes = {}
        self.current_theme = None
        self.theme_thread = None
        self.stop_event = None  # stop Event of the current theme thread run
        self.theme_change_lock = asyncio.Lock()
        self.master_brightness = 1.0
        self.frequency = 10  # Reduce update rate to 10 Hz
        self.paused_rooms = set()
        self.occupied_rooms = set()  # rooms wearing the OCCUPIED_MIX colour lock
        # room -> ((r, g, b), total): a game-won room holds this SOLID look —
        # no theme motion, no sway, no cap — until /api/room_vacated releases
        # it (set_room_occupied False). Set via set_room_win_hold (the VMM
        # victory hook in main.py).
        self.win_hold_rooms = {}
        self.room_profiles = {room: dict(profile)
                              for room, profile in ROOM_LIGHT_PROFILES.items()}
        self.theme_list = []
        self.previous_values = {}  # Store previous values for smoothing
        self.smoothing_factor = 0.2  # Adjust this value to control smoothing (0.0 to 1.0)
        self._step_lock = threading.RLock()
        self._theme_started_at = None
        self.load_themes()  # Load themes when initializing
        self.temporary_theme_values = {}  # Store temporary theme values
        # Attract mode: rotate through the dark looks on a dwell clock.
        self.attract_enabled = False
        self.attract_themes = list(ATTRACT_THEMES)
        self.attract_dwell_s = ATTRACT_DWELL_S
        self._attract_task = None
        self._last_theme_change = time.monotonic()
        self._band_side = {}  # per-room yellow-band snap hysteresis

    def load_themes(self):
        # Slow, dark looks for an open-faced night maze. Keep these in bounded
        # hue bands, with no random jitter or strobe/twinkle controls: the
        # result should breathe and travel, not flash.
        self.themes = {
            "DeepCanopy": {
                "duration": 3600,
                "transition_speed": 0.13,
                "color_variation": 0.45,
                "intensity_fluctuation": 0.42,
                "overall_brightness": 0.78,
                "room_transition_speed": 0.03,
                "color_wheel_speed": 0.0,
                "fairy_lights": 0.18,
                "moonbeam": 0.08,
                "jitter": 0.0,
                "base_hue": 0.30,  # shadow leaf
                "hue_range": 0.16,  # leaf to teal
                "saturation_min": 0.78,
                "saturation_max": 1.0,
                "value_min": 0.18,
                "value_max": 0.62
            },
            "EmberUndercroft": {
                "duration": 3600,
                "transition_speed": 0.11,
                "color_variation": 0.38,
                "intensity_fluctuation": 0.48,
                "overall_brightness": 0.72,
                "room_transition_speed": 0.025,
                "color_wheel_speed": 0.0,
                "wave_effect": 0.18,
                "sunset_glow": 0.0,
                "palm_shadow": 0.0,
                "jitter": 0.0,
                "base_hue": 0.00,  # coal red
                "hue_range": 0.08,  # red to copper, clamped away from yellow
                "saturation_min": 0.9,
                "saturation_max": 1.0,
                "value_min": 0.16,
                "value_max": 0.58
            },
            "CenoteDrift": {
                "duration": 3600,
                "transition_speed": 0.12,
                "color_variation": 0.42,
                "intensity_fluctuation": 0.46,
                "overall_brightness": 0.78,
                "room_transition_speed": 0.03,
                "color_wheel_speed": 0.0,
                "wave_effect": 0.34,
                "sunset_glow": 0.04,
                "palm_shadow": 0.0,
                "jitter": 0.0,
                "base_hue": 0.47,  # blue-green water
                "hue_range": 0.14,  # teal to blue
                "saturation_min": 0.82,
                "saturation_max": 1.0,
                "value_min": 0.18,
                "value_max": 0.64
            },
            "UltravioletVines": {
                "duration": 3600,
                "transition_speed": 0.105,
                "color_variation": 0.4,
                "intensity_fluctuation": 0.4,
                "overall_brightness": 0.76,
                "room_transition_speed": 0.028,
                "color_wheel_speed": 0.0,
                "fairy_lights": 0.14,
                "moonbeam": 0.06,
                "jitter": 0.0,
                "base_hue": 0.70,  # indigo
                "hue_range": 0.18,  # violet to magenta
                "saturation_min": 0.82,
                "saturation_max": 1.0,
                "value_min": 0.17,
                "value_max": 0.6
            },
            "MoonlitStone": {
                "duration": 3600,
                "transition_speed": 0.09,
                "color_variation": 0.34,
                "intensity_fluctuation": 0.34,
                "overall_brightness": 0.68,
                "room_transition_speed": 0.03,
                "color_wheel_speed": 0.0,
                "wave_effect": 0.18,
                "sunset_glow": 0.0,
                "palm_shadow": 0.0,
                "jitter": 0.0,
                "base_hue": 0.57,  # moon blue
                "hue_range": 0.16,  # cyan-blue to indigo
                "saturation_min": 0.8,
                "saturation_max": 0.96,
                "value_min": 0.14,
                "value_max": 0.5
            },
            "RitualAurora": {
                "duration": 3600,
                "transition_speed": 0.145,
                "color_variation": 0.5,
                "intensity_fluctuation": 0.5,
                "overall_brightness": 0.82,
                "room_transition_speed": 0.04,
                "color_wheel_speed": 0.0,
                "wave_effect": 0.24,
                "sunset_glow": 0.02,
                "palm_shadow": 0.0,
                "jitter": 0.0,
                "base_hue": 0.52,  # cyan
                "hue_range": 0.24,  # cyan through blue toward violet
                "saturation_min": 0.82,
                "saturation_max": 1.0,
                "value_min": 0.2,
                "value_max": 0.72
            }
        }
        self.theme_list = list(self.themes.keys())

    async def set_current_theme_async(self, theme_name):
        logger.info(f"Setting theme to: {theme_name}")
        if theme_name not in self.themes:
            logger.warning(f"Theme not found: {theme_name}")
            return False
        async with self.theme_change_lock:
            old_theme = self.current_theme
            await self.stop_current_theme_async()
            self.current_theme = theme_name
            # Each run gets its own Event so a stop can never be un-done for a
            # thread that outlived its join timeout (which would leave two
            # theme threads writing to the same fixtures).
            self.stop_event = threading.Event()
            self._theme_started_at = time.time()
            self.theme_thread = threading.Thread(target=self._run_theme,
                                                 args=(theme_name, self.stop_event), daemon=True)
            self.theme_thread.start()
            self.temporary_theme_values = {}
            self.previous_values = {}  # smoother starts clean — no old-theme drag
            # any set — attract's own or a manual one — restarts the dwell
            # clock, so an operator's pick gets its full stretch on stage
            self._last_theme_change = time.monotonic()
        logger.info(f"Theme changed from {old_theme} to: {theme_name}")
        return True

    async def stop_current_theme_async(self):
        if self.current_theme:
            logger.info(f"Stopping current theme: {self.current_theme}")
            if self.stop_event:
                self.stop_event.set()
            if self.theme_thread and self.theme_thread.is_alive():
                try:
                    await asyncio.wait_for(asyncio.to_thread(self.theme_thread.join), timeout=5.0)
                except asyncio.TimeoutError:
                    logger.warning("Theme thread join timed out after 5 seconds")
            self.theme_thread = None
            self.current_theme = None
            self._theme_started_at = None
            await asyncio.to_thread(self._reset_all_lights)
            # a deliberate stop buys a full dwell of dark before attract
            # relights the maze (and keeps rotation out of test windows)
            self._last_theme_change = time.monotonic()
            logger.info("Theme stopped and lights reset")

    # --- Attract mode -----------------------------------------------------

    def attract_state(self):
        threshold = ATTRACT_RELIGHT_S if self.current_theme is None else self.attract_dwell_s
        return {
            'enabled': self.attract_enabled,
            'dwell_s': self.attract_dwell_s,
            'themes': list(self.attract_themes),
            'current_theme': self.current_theme,
            'next_change_in_s': (max(0, round(threshold -
                                              (time.monotonic() - self._last_theme_change)))
                                 if self.attract_enabled else None),
        }

    async def set_attract(self, enabled, dwell_s=None, themes=None):
        """Turn the maze's self-running look rotation on/off. With no theme
        up, turning it on lights the first attract theme immediately."""
        if dwell_s:
            self.attract_dwell_s = max(60, int(dwell_s))
        if themes:
            known = [t for t in themes if t in self.themes]
            if known:
                self.attract_themes = known
        self.attract_enabled = bool(enabled)
        if self.attract_enabled:
            self._ensure_attract_task()
            if self.current_theme is None:
                await self._attract_advance()
        logger.info(f"Attract mode {'on' if self.attract_enabled else 'off'} "
                    f"(dwell {self.attract_dwell_s}s, themes {self.attract_themes})")
        return True

    def _ensure_attract_task(self):
        if self._attract_task is None or self._attract_task.done():
            self._attract_task = asyncio.create_task(self._attract_loop())

    async def _attract_loop(self):
        while self.attract_enabled:
            await asyncio.sleep(ATTRACT_TICK_S)
            if not self.attract_enabled:
                return
            try:
                threshold = (ATTRACT_RELIGHT_S if self.current_theme is None
                             else self.attract_dwell_s)
                if time.monotonic() - self._last_theme_change >= threshold:
                    await self._attract_advance()
            except Exception as e:
                logger.error(f"Attract rotation failed: {e}", exc_info=True)

    async def _attract_advance(self):
        pool = [t for t in self.attract_themes if t in self.themes]
        if not pool:
            logger.warning("Attract mode has no valid themes to rotate")
            return
        if self.current_theme in pool:
            next_theme = pool[(pool.index(self.current_theme) + 1) % len(pool)]
        else:
            next_theme = pool[0]
        logger.info(f"Attract mode -> {next_theme}")
        await self.set_current_theme_async(next_theme)

    async def set_next_theme_async(self):
        logger.info("Setting next theme")
        if not self.theme_list:
            logger.warning("No themes available")
            return None

        current_index = self.theme_list.index(self.current_theme) if self.current_theme in self.theme_list else -1
        for i in range(len(self.theme_list)):
            next_index = (current_index + i + 1) % len(self.theme_list)
            next_theme = self.theme_list[next_index]
            if next_theme != self.current_theme:
                success = await self.set_current_theme_async(next_theme)
                if success:
                    logger.info(f"Successfully set next theme to: {next_theme}")
                    return next_theme
        
        logger.error("Failed to set any theme after trying all available themes")
        return None

    def stop_current_theme(self):
        if self.current_theme:
            if self.stop_event:
                self.stop_event.set()
            if self.theme_thread and self.theme_thread.is_alive():
                self.theme_thread.join(timeout=5)
            self.theme_thread = None
            self.current_theme = None
            self._theme_started_at = None
            self._reset_all_lights()
            logger.info("Current theme stopped and all lights reset")

    def _reset_all_lights(self):
        for fixture_id in range(self.dmx_state_manager.num_fixtures):
            self.dmx_state_manager.reset_fixture(fixture_id)

    def _run_theme(self, theme_name, stop_event):
        theme_data = self.themes[theme_name]
        logger.info(f"Starting theme: {theme_name}")
        start_time = self._theme_started_at or time.time()
        last_update_time = 0
        try:
            while not stop_event.is_set():
                current_time = time.time() - start_time
                if current_time - last_update_time >= 1 / self.frequency:
                    with self._step_lock:
                        self._generate_and_apply_theme_step(theme_data, current_time)
                    last_update_time = current_time
                # Sleep to the next step deadline instead of polling at
                # ~1 kHz — the 1 ms spin woke this thread constantly and
                # taxed every await in the server via the GIL (live-night
                # lag, 2026-08-31). Cap keeps stop_event response <100 ms.
                next_due = (last_update_time + 1 / self.frequency
                            - (time.time() - start_time))
                time.sleep(min(0.1, max(0.005, next_due)))
        except Exception as e:
            logger.error(f"Error in theme {theme_name}: {str(e)}", exc_info=True)
        finally:
            logger.info(f"Theme {theme_name} stopped")

    def _generate_and_apply_theme_step(self, theme_data, current_time):
        room_layout = self.light_config_manager.get_room_layout()
        total_rooms = len(room_layout)
        all_room_channels = {}
        for room_index, (room, lights) in enumerate(room_layout.items()):
            if room in self.paused_rooms:
                logger.debug(f"Room {room} is paused, skipping theme application")
                continue
            if room in self.win_hold_rooms:
                # Won room: hold the solid victory look instead of the theme.
                all_room_channels[room] = self._apply_win_hold(room, lights)
                continue
            if room in self.occupied_rooms and room in ROOM_OCCUPIED_GRADIENTS:
                # Occupied gradient room: its own colour cycle owns the look.
                all_room_channels[room] = self._apply_room_gradient(room, lights)
                continue
            # a room's `rate` scales the theme clock: its colours breathe
            # at the tempo of its own soundtrack, not the maze average
            rate = (self.room_profiles.get(room) or {}).get('rate', 1.0)
            room_channels = generate_theme_values(theme_data, current_time * rate,
                                                  self.master_brightness,
                                                  room_index, total_rooms, self.temporary_theme_values)
            room_channels = self._apply_room_profile(room, room_channels)
            smoothed_channels = self._smooth_channels(room, room_channels)
            # guard AFTER the smoother: its RGB-space EMA passes through
            # grey when the hue swings — clamp what actually gets written
            if room != "Camp Sign":  # the sign's amber is its brand
                smoothed_channels = self._enforce_palette(smoothed_channels, room)
            all_room_channels[room] = smoothed_channels
            logger.debug(f"Generated channels for room {room}: {smoothed_channels}")
            self._apply_room_channels(room, lights, smoothed_channels, current_time * rate)
        
        if not all_room_channels:
            logger.warning("No room channels were generated. Check if all rooms are paused or if there's an issue with room layout.")
        
        return all_room_channels

    def set_room_light_profile(self, room, rgb=None, cap=None, mix=None):
        """Retune a room's ambient lens (the floor projection moving Cuddle
        Cross to a new theme). Unknown rooms get a profile created for them;
        omitted values keep whatever the room already had."""
        profile = self.room_profiles.setdefault(room, {})
        if rgb is not None:
            profile['rgb'] = tuple(rgb)
        if cap is not None:
            profile['cap'] = int(cap)
        if mix is not None:
            profile['mix'] = float(mix)
        logger.info(f"Room light profile for {room}: {profile}")

    def _apply_room_profile(self, room, channels):
        """Squeeze one room's theme step through its profile: hard brightness
        ceiling, no white, and a pull toward the room's own colour. The maze
        theme still drives the movement — this only changes how far and in
        which direction it may go."""
        profile = self.room_profiles.get(room)
        if not profile:
            return channels
        out = dict(channels)
        cap = profile.get('cap')
        if cap is not None:
            # scale INTO the ceiling rather than clamping at it: a bright
            # theme squeezed under a low cap keeps its whole swell shape
            # (a hard min() pinned capped rooms flat at the cap — no breathe)
            out['total_dimming'] = int(round(out.get('total_dimming', 0) * (cap / 255.0)))
        rgb = profile.get('rgb')
        if rgb:
            mix = (OCCUPIED_MIX if room in self.occupied_rooms
                   else profile.get('mix', 0.75))
            # Blend in HUE space, not RGB: an RGB lerp between two different
            # hues collapses into desaturated grey mud that renders as dim
            # WHITE lamps (Tim caught this live 2026-08-01 — Sparkle Pony's
            # pink lerped with theme green gave (115,108,93)). Rotating the
            # hue around the wheel keeps every mix fully saturated.
            r0 = out.get('r_dimming', 0) / 255.0
            g0 = out.get('g_dimming', 0) / 255.0
            b0 = out.get('b_dimming', 0) / 255.0
            th, ts, tv = colorsys.rgb_to_hsv(r0, g0, b0)
            rh, rs, _ = colorsys.rgb_to_hsv(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
            delta = (rh - th + 0.5) % 1.0 - 0.5   # shortest way around the wheel
            hue = (th + delta * mix) % 1.0
            sat = max(ts, rs, 0.8)                 # never grey
            r1, g1, b1 = colorsys.hsv_to_rgb(hue, sat, max(tv, 0.05))
            out['r_dimming'] = int(r1 * 255)
            out['g_dimming'] = int(g1 * 255)
            out['b_dimming'] = int(b1 * 255)
        out['w_dimming'] = 0  # the projection room never gets white
        return out

    def _enforce_palette(self, channels, room_key=''):
        """The HARD floor under Tim's rule: no bright yellow, no white, no
        grey-white, out of the theme path — ever. CONTINUOUS clamps only: the
        first version used step thresholds, and colours hovering around a
        boundary during a theme transition alternated clamped/unclamped —
        the start-of-theme flicker Tim saw. A saturation floor and a yellow
        band push change smoothly with their input, so no frame-to-frame
        jumps."""
        out = dict(channels)
        out['w_dimming'] = 0
        r = out.get('r_dimming', 0); g = out.get('g_dimming', 0); b = out.get('b_dimming', 0)
        if max(r, g, b) <= 3:
            return out
        h, sat, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
        changed = False
        if sat < 0.45:            # grey/pastel -> saturated (continuous floor)
            sat = 0.45
            changed = True
        if YELLOW_ARC[0] <= h <= YELLOW_ARC[1]:   # -> a STICKY edge (orange/green)
            # Sticky so a hue loitering near the split doesn't flip edges frame
            # to frame; it re-decides only once clearly on one side.
            side = self._band_side.get(room_key)
            if side is None or abs(h - YELLOW_SPLIT) > 0.02:
                side = 'lo' if h < YELLOW_SPLIT else 'hi'
                self._band_side[room_key] = side
            h, _ = snap_hue_out_of_yellow(h, side)
            changed = True
        if changed:
            r1, g1, b1 = colorsys.hsv_to_rgb(h, sat, v)
            out['r_dimming'] = int(r1 * 255)
            out['g_dimming'] = int(g1 * 255)
            out['b_dimming'] = int(b1 * 255)
        return out

    def _smooth_channels(self, room, new_channels):
        if room not in self.previous_values:
            self.previous_values[room] = new_channels
            return new_channels

        smoothed_channels = {}
        for channel, value in new_channels.items():
            prev_value = self.previous_values[room].get(channel, value)
            smoothed_value = prev_value + (value - prev_value) * self.smoothing_factor
            smoothed_channels[channel] = int(smoothed_value)

        self.previous_values[room] = smoothed_channels
        return smoothed_channels

    def set_room_occupied(self, room, occupied):
        """Presence half of the triggers.json occupancy contract: entry pins
        the room's mix to OCCUPIED_MIX, vacate releases it. Set ops only, so
        it is safe from any thread and repeats are no-ops. Vacate also ends
        any win hold — a won room stays solid green only while its winners
        are still inside."""
        if occupied:
            self.occupied_rooms.add(room)
        else:
            self.occupied_rooms.discard(room)
            if self.win_hold_rooms.pop(room, None) is not None:
                logger.info(f"Room {room} win hold released")
                if not self.current_theme:
                    # No theme to repaint over the held frame (the dark
                    # relight window): a vacated won room must not stay lit
                    # solid green alone in a dark maze.
                    for light in self.light_config_manager.get_room_layout().get(room, []):
                        fixture_id = (light['start_address'] - 1) // 8
                        if not self.interrupt_handler.is_interrupted(fixture_id):
                            self.dmx_state_manager.reset_fixture(fixture_id)
        logger.info(f"Room {room} {'occupied — colour lock on' if occupied else 'vacated — colour lock off'}")

    def set_room_win_hold(self, room, rgb, total=200):
        """Pin a room to a SOLID look — no theme motion, no per-fixture sway,
        no profile cap — until set_room_occupied(room, False) releases it
        (the /api/room_vacated path). The game-won state: VMM's victory hook
        sets solid green here the moment the win effect starts, and the room
        wears it from the effect's last frame until the radar reports empty.
        Runs even with no theme up: the hold is painted once immediately, so
        a won room can't sit dark waiting for the next theme tick."""
        self.win_hold_rooms[room] = (tuple(rgb), int(total))
        logger.info(f"Room {room} win hold: rgb={tuple(rgb)} total={int(total)}")
        lights = self.light_config_manager.get_room_layout().get(room)
        if lights and room not in self.paused_rooms:
            with self._step_lock:
                self._apply_win_hold(room, lights)

    def _apply_win_hold(self, room, lights):
        """Write the room's held solid frame to every non-interrupted fixture.
        Deliberately bypasses profile cap/mix, smoothing and sway: 'solid'
        means every frame is identical until the hold is released."""
        (r, g, b), total = self.win_hold_rooms[room]
        channels = {'total_dimming': total, 'r_dimming': r, 'g_dimming': g,
                    'b_dimming': b, 'w_dimming': 0, 'total_strobe': 0,
                    'function_selection': 0, 'function_speed': 0}
        for light in lights:
            self._write_fixture_channels(light, channels)
        return channels

    def _apply_room_gradient(self, room, lights):
        """Paint one tick of an occupied room's colour cycle
        (ROOM_OCCUPIED_GRADIENTS): hue ping-pongs hue_lo..hue_hi on the
        monotonic clock, full saturation, steady brightness — the motion IS
        the hue travel. Each fixture trails the previous by fixture_phase_s.
        Skips interrupted fixtures so press flashes play over it."""
        cfg = ROOM_OCCUPIED_GRADIENTS[room]
        period = cfg['period_s']
        half = period / 2.0
        now = time.monotonic()
        channels = None
        for k, light in enumerate(lights):
            t = (now - k * cfg['fixture_phase_s']) % period
            frac = t / half if t < half else (period - t) / half
            hue = (cfg['hue_lo'] + (cfg['hue_hi'] - cfg['hue_lo']) * frac) % 1.0
            r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            channels = {'total_dimming': cfg['total'],
                        'r_dimming': int(r * 255), 'g_dimming': int(g * 255),
                        'b_dimming': int(b * 255), 'w_dimming': 0,
                        'total_strobe': 0, 'function_selection': 0,
                        'function_speed': 0}
            self._write_fixture_channels(light, channels)
        return channels

    def _write_fixture_channels(self, light, channels):
        """Map a channel dict through the fixture's model and write it,
        unless an effect currently owns the fixture."""
        fixture_id = (light['start_address'] - 1) // 8
        if self.interrupt_handler.is_interrupted(fixture_id):
            return
        light_model = self.light_config_manager.get_light_config(light['model'])
        fixture_values = [0] * 8
        for channel, value in channels.items():
            if channel in light_model['channels']:
                fixture_values[light_model['channels'][channel]] = value
        self.dmx_state_manager.update_fixture(fixture_id, fixture_values)

    def pause_theme_for_room(self, room):
        self.paused_rooms.add(room)
        logger.info(f"Theme paused for room: {room}")

    def resume_theme_for_room(self, room):
        self.paused_rooms.discard(room)
        logger.info(f"Theme resumed for room: {room}")
        self._apply_room_theme_now(room)

    def _apply_room_theme_now(self, room):
        room_layout = self.light_config_manager.get_room_layout()
        lights = room_layout.get(room)
        if not lights:
            return
        if room in self.win_hold_rooms:
            # A won room resumes to its held solid look, theme or no theme —
            # this is what makes the victory effect hand off seamlessly.
            with self._step_lock:
                self._apply_win_hold(room, lights)
            return
        if room in self.occupied_rooms and room in ROOM_OCCUPIED_GRADIENTS:
            # An occupied gradient room resumes straight onto its cycle (a
            # press flash just ended); the theme loop keeps it moving.
            with self._step_lock:
                self._apply_room_gradient(room, lights)
            return
        if not self.current_theme:
            return
        theme_data = self.themes.get(self.current_theme)
        if not theme_data:
            return
        started_at = self._theme_started_at or time.time()
        current_time = time.time() - started_at
        rooms = list(room_layout.keys())
        room_index = rooms.index(room)
        total_rooms = len(rooms)
        profile = self.room_profiles.get(room) or {}
        rate = profile.get('rate', 1.0)
        with self._step_lock:
            room_channels = generate_theme_values(theme_data, current_time * rate,
                                                  self.master_brightness,
                                                  room_index, total_rooms,
                                                  self.temporary_theme_values)
            room_channels = self._apply_room_profile(room, room_channels)
            smoothed_channels = self._smooth_channels(room, room_channels)
            if room != "Camp Sign":
                smoothed_channels = self._enforce_palette(smoothed_channels, room)
            self._apply_room_channels(room, lights, smoothed_channels, current_time * rate)

    def _apply_room_channels(self, room, lights, room_channels, room_time=0.0):
        # DMX means every fixture is its own lamp: give each one an offset
        # breathing phase so multi-fixture rooms cross-fade between pars and
        # the sign's 24 zones ripple, instead of one flat value per room.
        for k, light in enumerate(lights):
            sway = 0.78 + 0.22 * math.sin(room_time * 0.55 + k * 2.1)
            channels = dict(room_channels)
            channels['total_dimming'] = int(channels.get('total_dimming', 0) * sway)
            room_channels_fixture = channels
            start_address = light['start_address']
            light_model = self.light_config_manager.get_light_config(light['model'])
            fixture_id = (start_address - 1) // 8
            if self.interrupt_handler.is_interrupted(fixture_id):
                logger.debug(f"Fixture {fixture_id} in room {room} is interrupted, skipping update")
                continue
            fixture_values = [0] * 8
            for channel, value in room_channels_fixture.items():
                if channel in light_model['channels']:
                    channel_offset = light_model['channels'][channel]
                    fixture_values[channel_offset] = value
            self.dmx_state_manager.update_fixture(fixture_id, fixture_values)

    def set_master_brightness(self, brightness):
        self.master_brightness = max(0.0, min(1.0, brightness))
        logger.info(f"Master brightness set to {self.master_brightness}")

    def get_all_themes(self):
        return self.themes

    async def update_theme_value(self, control_id, value):
        if self.current_theme:
            self.temporary_theme_values[control_id] = value
            logger.info(f"Updated temporary value for {control_id} to {value} for current theme")
            return True
        else:
            logger.warning("No current theme to update")
            return False
