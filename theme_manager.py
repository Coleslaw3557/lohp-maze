import colorsys
import logging
import math
import time
import threading
import asyncio
from effect_utils import generate_theme_values

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
    "Entrance": {"cap": 235, "rgb": (110, 30, 200), "mix": 0.45, "rate": 0.7},
    "Gate": {"cap": 235, "rgb": (255, 90, 0), "mix": 0.45, "rate": 0.9},
    "Cop Dodge": {"cap": 240, "rgb": (30, 80, 255), "mix": 0.45, "rate": 1.3},
    "Photo Bomb Room": {"cap": 235, "rgb": (255, 40, 170), "mix": 0.45, "rate": 1.1},
    "Porto Room": {"cap": 230, "rgb": (60, 220, 50), "mix": 0.45, "rate": 0.8},
    "Bike Lock Room": {"cap": 235, "rgb": (230, 80, 20), "mix": 0.45, "rate": 1.0},
    "Guy Line Climb": {"cap": 225, "rgb": (30, 180, 90), "mix": 0.5, "rate": 0.6},
    "Monkey Room": {"cap": 235, "rgb": (190, 50, 230), "mix": 0.45, "rate": 1.2},
    "No Friends Monday": {"cap": 245, "rgb": (255, 60, 120), "mix": 0.4, "rate": 1.1},
    "Sparkle Pony Room": {"cap": 235, "rgb": (255, 70, 200), "mix": 0.45, "rate": 1.0},
    "Vertical Moop March": {"cap": 235, "rgb": (90, 210, 60), "mix": 0.45, "rate": 0.9},
    "Deep Playa Handshake": {"cap": 240, "rgb": (200, 30, 255), "mix": 0.45, "rate": 1.4},
    "Temple Room": {"cap": 230, "rgb": (40, 160, 140), "mix": 0.5, "rate": 0.7},
    "Exit": {"cap": 240, "rgb": (60, 230, 90), "mix": 0.4, "rate": 1.0},
}

# Attract mode (Tim 2026-08-01): with nobody driving, the maze runs these
# mossy/Mayan looks on its own and rolls to the next every ATTRACT_DWELL_S.
# A manual /api/set_theme keeps rotation alive but restarts the dwell clock —
# the maze never gets stuck on one look because someone tapped the orb.
ATTRACT_THEMES = ["MossyTemple", "JungleCanopy", "TorchlitRuin", "CenoteNight"]
ATTRACT_DWELL_S = 15 * 60
ATTRACT_TICK_S = 20
# After a deliberate stop the maze stays dark this long, then attract
# relights it — long enough that a stop reads as intentional (and stays out
# of test windows), short enough that the maze never sits dark all night.
ATTRACT_RELIGHT_S = 180


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
        self.room_profiles = {room: dict(profile)
                              for room, profile in ROOM_LIGHT_PROFILES.items()}
        self.theme_list = []
        self.previous_values = {}  # Store previous values for smoothing
        self.smoothing_factor = 0.2  # Adjust this value to control smoothing (0.0 to 1.0)
        self.load_themes()  # Load themes when initializing
        self.temporary_theme_values = {}  # Store temporary theme values
        # Attract mode: rotate through the mossy looks on a dwell clock.
        self.attract_enabled = False
        self.attract_themes = list(ATTRACT_THEMES)
        self.attract_dwell_s = ATTRACT_DWELL_S
        self._attract_task = None
        self._last_theme_change = time.monotonic()
        self._band_side = {}  # per-room yellow-band snap hysteresis

    def load_themes(self):
        # Load themes with more dynamic and vibrant settings
        self.themes = {
            "NeonNightlife": {
                "duration": 3600,  # 1 hour
                "transition_speed": 0.1,
                "color_variation": 1.0,
                "intensity_fluctuation": 0.8,
                "overall_brightness": 0.9,
                "room_transition_speed": 0.05,
                "color_wheel_speed": 0.2,
                "neon_pulse": 0.9,
                "strobe_frequency": 0.3,
                "color_shift": 0.7,
                "base_hue": 0.8,  # Purple
                "hue_range": 1.0,  # Full spectrum
                "saturation_min": 0.7,
                "saturation_max": 1.0,
                "value_min": 0.6,
                "value_max": 1.0
            },
            "TropicalParadise": {
                "duration": 3600,  # 1 hour
                "transition_speed": 0.08,
                "color_variation": 0.9,
                "intensity_fluctuation": 0.6,
                "overall_brightness": 0.85,
                "room_transition_speed": 0.04,
                "color_wheel_speed": 0.15,
                "wave_effect": 0.7,
                "sunset_glow": 0.8,
                "palm_shadow": 0.5,
                "base_hue": 0.1,  # Orange
                "hue_range": 0.3,  # Orange to Green
                "saturation_min": 0.6,
                "saturation_max": 1.0,
                "value_min": 0.7,
                "value_max": 0.95
            },
            "CyberPunk": {
                "duration": 3600,  # 1 hour
                "transition_speed": 0.12,
                "color_variation": 1.0,
                "intensity_fluctuation": 0.9,
                "overall_brightness": 0.95,
                "room_transition_speed": 0.06,
                "color_wheel_speed": 0.25,
                "neon_flicker": 0.8,
                "data_stream": 0.7,
                "hologram_effect": 0.6,
                "base_hue": 0.6,  # Blue
                "hue_range": 0.8,  # Blue to Pink
                "saturation_min": 0.8,
                "saturation_max": 1.0,
                "value_min": 0.7,
                "value_max": 1.0
            },
            "EnchantedForest": {
                "duration": 3600,  # 1 hour
                "transition_speed": 0.06,
                "color_variation": 0.8,
                "intensity_fluctuation": 0.7,
                "overall_brightness": 0.8,
                "room_transition_speed": 0.03,
                "color_wheel_speed": 0.1,
                "fairy_lights": 0.6,
                "moonbeam": 0.5,
                "firefly_effect": 0.7,
                "base_hue": 0.3,  # Green
                "hue_range": 0.4,  # Green to Purple
                "saturation_min": 0.5,
                "saturation_max": 0.9,
                "value_min": 0.6,
                "value_max": 0.9
            },
            "CosmicVoyage": {
                "duration": 3600,  # 1 hour
                "transition_speed": 0.15,
                "color_variation": 1.0,
                "intensity_fluctuation": 0.9,
                "overall_brightness": 0.9,
                "room_transition_speed": 0.07,
                "color_wheel_speed": 0.3,
                "starfield_twinkle": 0.8,
                "nebula_swirl": 0.7,
                "wormhole_effect": 0.6,
                "base_hue": 0.7,  # Indigo
                "hue_range": 1.0,  # Full spectrum
                "saturation_min": 0.7,
                "saturation_max": 1.0,
                "value_min": 0.5,
                "value_max": 1.0
            },
            "BladeRunner": {
                "duration": 3600,  # 1 hour
                "transition_speed": 0.08,
                "color_variation": 0.7,
                "intensity_fluctuation": 0.6,
                "overall_brightness": 0.7,
                "room_transition_speed": 0.05,
                "color_wheel_speed": 0.1,
                "neon_flicker": 0.4,
                "rain_effect": 0.6,
                "smog_effect": 0.5,
                "base_hue": 0.6,  # Blue
                "hue_range": 0.3,  # Blue to Purple
                "saturation_min": 0.6,
                "saturation_max": 0.9,
                "value_min": 0.3,
                "value_max": 0.9
            },
            # --- The attract-mode set (Tim 2026-08-01): the maze's own mossy
            # Mayan looks. All four hold color_wheel_speed at 0 so the hue
            # stays inside its palette band instead of touring the wheel, and
            # keep value low — the room profiles then colour each room to its
            # own sound over these. Motion reuses the generator's existing
            # branches: neon_flicker = torch flicker, fairy_lights =
            # fireflies, wave_effect = water.
            "MossyTemple": {
                "duration": 3600,
                "transition_speed": 0.4,
                "color_variation": 0.6,
                "intensity_fluctuation": 0.7,
                "overall_brightness": 0.9,
                "room_transition_speed": 0.03,
                "color_wheel_speed": 0.0,
                "jitter": 0.15,
                "base_hue": 0.38,  # moss green (floor raised: wobble was dipping into yellow)
                "hue_range": 0.10,  # green to teal
                "saturation_min": 0.75,
                "saturation_max": 1.0,
                "value_min": 0.3,
                "value_max": 0.9
            },
            "JungleCanopy": {
                "duration": 3600,
                "transition_speed": 0.5,
                "color_variation": 0.7,
                "intensity_fluctuation": 0.6,
                "overall_brightness": 0.9,
                "room_transition_speed": 0.04,
                "color_wheel_speed": 0.0,
                "fairy_lights": 0.5,   # fireflies through the leaves
                "moonbeam": 0.3,
                "firefly_effect": 0.6,
                "jitter": 0.15,
                "base_hue": 0.34,  # leaf green (floor raised: wobble was dipping into yellow)
                "hue_range": 0.10,
                "saturation_min": 0.7,
                "saturation_max": 1.0,
                "value_min": 0.3,
                "value_max": 0.9
            },
            "TorchlitRuin": {
                "duration": 3600,
                "transition_speed": 0.45,
                "color_variation": 0.5,
                "intensity_fluctuation": 0.6,
                "overall_brightness": 0.85,
                "room_transition_speed": 0.03,
                "color_wheel_speed": 0.0,
                "neon_flicker": 0.9,   # generator MULTIPLIES value by this — 0.9 = bright with a gutter; 0.35 crushed it to a third
                "data_stream": 0.15,
                "jitter": 0.15,
                "base_hue": 0.045,  # ember copper — value stays low so it
                "hue_range": 0.05,  # reads torchlight, never bright yellow
                "saturation_min": 0.9,
                "saturation_max": 1.0,
                "value_min": 0.25,
                "value_max": 0.75
            },
            "CenoteNight": {
                "duration": 3600,
                "transition_speed": 0.45,
                "color_variation": 0.6,
                "intensity_fluctuation": 0.7,
                "overall_brightness": 0.9,
                "room_transition_speed": 0.03,
                "color_wheel_speed": 0.0,
                "wave_effect": 0.5,    # water lapping the cave wall
                "sunset_glow": 0.15,
                "palm_shadow": 0.0,
                "jitter": 0.15,
                "base_hue": 0.5,   # cenote teal
                "hue_range": 0.1,
                "saturation_min": 0.8,
                "saturation_max": 1.0,
                "value_min": 0.28,
                "value_max": 0.8
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
            await asyncio.to_thread(self._reset_all_lights)
            # a deliberate stop buys a full dwell of dark before attract
            # relights the maze (and keeps rotation out of test windows)
            self._last_theme_change = time.monotonic()
            logger.info("Theme stopped and lights reset")

    # --- Attract mode -----------------------------------------------------

    def attract_state(self):
        return {
            'enabled': self.attract_enabled,
            'dwell_s': self.attract_dwell_s,
            'themes': list(self.attract_themes),
            'current_theme': self.current_theme,
            'next_change_in_s': (max(0, round(self.attract_dwell_s -
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
            self._reset_all_lights()
            logger.info("Current theme stopped and all lights reset")

    def _reset_all_lights(self):
        for fixture_id in range(self.dmx_state_manager.num_fixtures):
            self.dmx_state_manager.reset_fixture(fixture_id)

    def _run_theme(self, theme_name, stop_event):
        theme_data = self.themes[theme_name]
        logger.info(f"Starting theme: {theme_name}")
        start_time = time.time()
        last_update_time = 0
        try:
            while not stop_event.is_set():
                current_time = time.time() - start_time
                if current_time - last_update_time >= 1 / self.frequency:
                    self._generate_and_apply_theme_step(theme_data, current_time)
                    last_update_time = current_time
                time.sleep(0.001)  # Small sleep to prevent CPU hogging
        except Exception as e:
            logger.error(f"Error in theme {theme_name}: {str(e)}", exc_info=True)
        finally:
            logger.info(f"Theme {theme_name} stopped")

    def _generate_and_apply_theme_step(self, theme_data, current_time):
        room_layout = self.light_config_manager.get_room_layout()
        total_rooms = len(room_layout)
        all_room_channels = {}
        for room_index, (room, lights) in enumerate(room_layout.items()):
            if room not in self.paused_rooms:
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
            else:
                logger.debug(f"Room {room} is paused, skipping theme application")
        
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
            mix = profile.get('mix', 0.75)
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
        if 0.09 <= h <= 0.19:     # yellow band -> a sticky edge (orange/green)
            side = self._band_side.get(room_key)
            if side is None or abs(h - 0.1425) > 0.012:
                side = 'lo' if h < 0.1425 else 'hi'
                self._band_side[room_key] = side
            h = 0.075 if side == 'lo' else 0.205
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

    def pause_theme_for_room(self, room):
        self.paused_rooms.add(room)
        logger.info(f"Theme paused for room: {room}")

    def resume_theme_for_room(self, room):
        self.paused_rooms.discard(room)
        logger.info(f"Theme resumed for room: {room}")

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
