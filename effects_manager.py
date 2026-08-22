import colorsys
import logging
import asyncio
from collections import defaultdict
from contextlib import AsyncExitStack
from effects import (
    create_lightning_effect, create_police_lights_effect, create_gate_inspection_effect,
    create_gate_greeters_effect, create_wrong_answer_effect, create_correct_answer_effect,
    create_backtrack_effect, create_entrance_effect, create_exit_effect,
    create_spark_pony_effect,
    create_porto_standby_effect, create_porto_hit_effect, create_cuddle_puddle_effect,
    create_photobomb_bg_effect, create_photobomb_spot_effect, create_deep_playa_bg_effect,
    create_deep_playa_hit_effect, create_image_enhancement_effect, create_bike_lock_room_effect,
    create_bike_lock_entry_effect, create_no_friends_monday_effect, create_lightning_storm_effect,
    create_photobomb_shot_effect, create_photobomb_landed_effect,
    create_monkey_business_effect,
    create_shrine_guard_effect, create_moop_march_effect, create_moop_victory_effect,
    create_moop_press_flash_effect, create_temple_wake_effect,
)
from effects.moop_march import MOOP_BUTTON_COLORS
from effects import (
    create_cuddle_lava_hit_effect, create_cuddle_lava_breach_effect,
    create_cuddle_chamber_trap_effect, palette_for
)
from theme_manager import ThemeManager
from effect_utils import get_effect_step_values, palette_clamp_frame, snap_hue_out_of_yellow
from interrupt_handler import InterruptHandler
from room_answer_pools import ANSWER_EFFECTS, ROOM_ANSWER_POOL_PREFIXES, answer_pool_name

logger = logging.getLogger(__name__)

CUDDLE_ROOM = "Cuddle Cross"  # the projection room; its lights follow the floor show
NO_SHARED_ANSWER_AUDIO_FALLBACK_ROOMS = {"Bike Lock Room"}
SHARED_ANSWER_AUDIO_ROOMS = {"Vertical Moop March"}


class EffectsManager:
    def __init__(self, light_config_manager, dmx_state_manager, remote_host_manager, audio_manager):
        self.light_config_manager = light_config_manager
        self.dmx_state_manager = dmx_state_manager
        self.remote_host_manager = remote_host_manager
        self.audio_manager = audio_manager
        self.interrupt_handler = InterruptHandler(dmx_state_manager)
        self.theme_manager = ThemeManager(dmx_state_manager, light_config_manager, self.interrupt_handler)
        self.effect_tasks = {}  # room -> asyncio.Task of the running effect
        self.room_locks = defaultdict(asyncio.Lock)  # serializes effect start/stop per room
        self.effects = {
            "Lightning": create_lightning_effect(),
            "PoliceLights": create_police_lights_effect(),
            "GateInspection": create_gate_inspection_effect(),
            "GateGreeters": create_gate_greeters_effect(),
            "WrongAnswer": create_wrong_answer_effect(),
            "Backtrack": create_backtrack_effect(),
            "CorrectAnswer": create_correct_answer_effect(),
            "Entrance": create_entrance_effect(),
            "Exit": create_exit_effect(),
            "SparkPony": create_spark_pony_effect(),
            "PortoStandBy": create_porto_standby_effect(),
            "PortoHit": create_porto_hit_effect(),
            "CuddlePuddle": create_cuddle_puddle_effect(),
            "PhotoBomb-BG": create_photobomb_bg_effect(),
            "PhotoBomb-Spot": create_photobomb_spot_effect(),
            "DeepPlaya-BG": create_deep_playa_bg_effect(),
            "DeepPlaya-Hit": create_deep_playa_hit_effect(),
            "ImageEnhancement": create_image_enhancement_effect(),
            "BikeLockRoom": create_bike_lock_room_effect(),
            "BikeLock-Entry": create_bike_lock_entry_effect(),
            "NoFriendsMonday": create_no_friends_monday_effect(),
            "LightningStorm": create_lightning_storm_effect(),
            "PhotoBomb-Shot": create_photobomb_shot_effect(),
            "PhotoBomb-Landed": create_photobomb_landed_effect(),
            "MonkeyBusiness": create_monkey_business_effect(),
            "ShrineGuard": create_shrine_guard_effect(),
            "MoopMarch": create_moop_march_effect(),
            "TempleWake": create_temple_wake_effect(),
            # Cuddle Cross accents, fired by the floor projection's own events
            # (floor_show_manager.py), not by a sensor
            "Cuddle-Lava-Hit": create_cuddle_lava_hit_effect(),
            "Cuddle-Lava-Breach": create_cuddle_lava_breach_effect(),
            "Cuddle-Chamber-Trap": create_cuddle_chamber_trap_effect(),
        }
        self._register_room_answer_effects()
        # VMM game lighting (Tim 2026-08-17): while occupied the room runs its
        # own green/blue/red gradient (theme_manager ROOM_OCCUPIED_GRADIENTS —
        # the MoopMarch entry effect is a no_lights marker), each button press
        # flashes THAT button's identity colour whole-room, and the win
        # overrides the pool registration with a bloom that lands on the solid
        # win hold (main.py hook). The game still POSTs "CorrectAnswer" with
        # the button's trigger_name, so the shared audio pool, WS clients and
        # telemetry are untouched — only the light is swapped below.
        self.effects["VerticalMoopMarch-RightAnswer"] = create_moop_victory_effect()
        self.effects["VerticalMoopMarch-Press"] = create_moop_press_flash_effect()
        for i, (button, (rgb, w, label)) in enumerate(MOOP_BUTTON_COLORS.items(), 1):
            self.effects[f"VerticalMoopMarch-Press{i}"] = \
                create_moop_press_flash_effect(rgb, w, label)
        # (room, requested effect) -> effect name whose LIGHT plays in that
        # room instead. Audio, telemetry and WS payloads keep the requested
        # name; only apply_effect_to_room's lighting data is swapped. The
        # trigger-keyed map wins when the POST carries a matching
        # trigger_name; the room-keyed map is the unlabeled fallback.
        self.room_light_overrides = {
            ("Vertical Moop March", "CorrectAnswer"): "VerticalMoopMarch-Press",
        }
        self.room_trigger_light_overrides = {
            ("Vertical Moop March", "CorrectAnswer", button): f"VerticalMoopMarch-Press{i}"
            for i, button in enumerate(MOOP_BUTTON_COLORS, 1)
        }
        self._enforce_effect_palette()
        # effect_name -> {'start': fn(room), 'cancel': fn(room)} side-channel for
        # non-lighting actions tied to an effect run (the Photo Bomb camera)
        self.effect_hooks = {}
        self.floor_theme = None
        logger.info(f"Initialized {len(self.effects)} effects")

    # Effects that genuinely need bright white throughout. Camera effects use
    # narrow `palette_exempt_windows` instead, so their countdowns and afterglows
    # still obey the no-white/no-yellow palette rule.
    PALETTE_EXEMPT = {"Lightning", "LightningStorm"}

    def _palette_exempt_at(self, effect, t):
        if effect.get("palette_exempt"):
            return True
        for start, end in effect.get("palette_exempt_windows", ()):
            if start <= t <= end:
                return True
        return False

    def _enforce_effect_palette(self):
        """Clamp every non-exempt effect step at registration: white capped
        low, yellow pulled to orange, pale near-white resaturated toward its
        dominant colour. Entry/interaction effects keep their choreography
        but wear the maze palette — enforced here so no individual effect
        file can drift bright again."""
        for name, effect in self.effects.items():
            if name in self.PALETTE_EXEMPT:
                effect["palette_exempt"] = True  # playback guard passes these through
                continue
            for step in effect.get("steps", []):
                if self._palette_exempt_at(effect, step.get("time", 0)):
                    continue
                ch = step["channels"]
                ch["w_dimming"] = min(ch.get("w_dimming", 0), 45)
                r = ch.get("r_dimming", 0); g = ch.get("g_dimming", 0); b = ch.get("b_dimming", 0)
                if r > 150 and g > 0.55 * r and b < 80:
                    ch["g_dimming"] = g = int(r * 0.42)  # yellow -> orange
                hi = max(r, g, b)
                if hi > 150 and min(r, g, b) > 0.62 * hi:  # pale wash -> saturate
                    for key, v in (("r_dimming", r), ("g_dimming", g), ("b_dimming", b)):
                        if v != hi:
                            ch[key] = int(v * 0.4)
                # Backstop on the values that actually ship. The two rules above
                # are deliberately untouched — they shape the maze's warm tones
                # and every effect was authored against them — but between them
                # they only catch BRIGHT red-dominant yellows, so authored dim
                # yellow and yellow-green (moop march's khaki, monkey's amber)
                # still reached the pars. Anything left inside the arc lands on
                # its nearer edge; anything outside is passed through untouched.
                r = ch.get("r_dimming", 0); g = ch.get("g_dimming", 0); b = ch.get("b_dimming", 0)
                if max(r, g, b) > 10:
                    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
                    h, snapped = snap_hue_out_of_yellow(h)
                    if snapped:
                        r1, g1, b1 = colorsys.hsv_to_rgb(h, s, v)
                        ch["r_dimming"] = int(r1 * 255)
                        ch["g_dimming"] = int(g1 * 255)
                        ch["b_dimming"] = int(b1 * 255)

    def _register_room_answer_effects(self):
        """Room-local answer pools reuse the shared answer light effects.

        Empty room pools are valid placeholders in audio_config.json and the
        audio console. When existing game code still fires the shared
        CorrectAnswer/WrongAnswer effect, _audio_effect_name() below prefers the
        room pool only once it has files, so placeholders do not make answers
        silently lose their fallback chime/fail sounds.
        """
        for room in ROOM_ANSWER_POOL_PREFIXES:
            right = create_correct_answer_effect()
            right['description'] = f"{room} right-answer cue"
            self.effects[answer_pool_name(room, "CorrectAnswer")] = right

            wrong = create_wrong_answer_effect()
            wrong['description'] = f"{room} wrong-answer cue"
            self.effects[answer_pool_name(room, "WrongAnswer")] = wrong

    def _audio_effect_name(self, room, effect_name):
        if effect_name not in ANSWER_EFFECTS:
            return effect_name
        candidate = answer_pool_name(room, effect_name)
        if not candidate:
            return effect_name
        if room in SHARED_ANSWER_AUDIO_ROOMS:
            return effect_name
        config = self.audio_manager.get_audio_config(candidate)
        if room in NO_SHARED_ANSWER_AUDIO_FALLBACK_ROOMS:
            return candidate
        return candidate if config.get('audio_files') else effect_name

    def set_floor_theme(self, theme):
        """Point Cuddle Cross's lights at the floor projection's current theme
        (floor_show_manager.py). Rebuilds the room's entry swell in the theme's
        palette and hands the ambient colour/ceiling to the maze theme, so the
        projection room matches the deck whether an effect is running or not."""
        if theme == self.floor_theme:
            return False
        self.floor_theme = theme
        self.effects["CuddlePuddle"] = create_cuddle_puddle_effect(theme)
        pal = palette_for(theme)
        self.theme_manager.set_room_light_profile(
            CUDDLE_ROOM, rgb=pal['ambient'], cap=pal['cap'])
        logger.info(f"Cuddle Cross lights following floor theme: {theme}")
        return True

    def register_effect_hooks(self, effect_name, on_start=None, on_cancel=None):
        """Attach callbacks to an effect's lifecycle. ``on_start`` fires when a
        run actually begins (post-takeover, inside the effect task); ``on_cancel``
        fires only if that run is cancelled/superseded before completing. Both
        must be synchronous and quick — they run on the event loop."""
        self.effect_hooks[effect_name] = {'start': on_start, 'cancel': on_cancel}

    def get_effect(self, effect_name):
        return self.effects.get(effect_name)

    def get_all_effects(self):
        return self.effects

    def get_effects_list(self):
        return {name: data.get('description', 'No description available')
                for name, data in self.effects.items()}

    def _room_fixture_ids(self, room, role=None):
        """Fixture ids for a room. With `role`, only the fixtures tagged that
        role in light_config.json — and when a room has none tagged (every
        one-par room), all of them, so reactions still land everywhere."""
        lights = self.light_config_manager.get_room_layout().get(room, [])
        if role:
            tagged = [light for light in lights if light.get('role') == role]
            if tagged:
                lights = tagged
        return [(light['start_address'] - 1) // 8 for light in lights]

    async def apply_effect_to_room(self, room, effect_name, effect_data=None,
                                   trigger_name=None):
        if effect_data is None:
            effect_data = self.get_effect(effect_name)
        if not effect_data:
            return False, f"{effect_name} effect not found"
        override_name = None
        if trigger_name:
            override_name = self.room_trigger_light_overrides.get(
                (room, effect_name, trigger_name))
        if not override_name:
            override_name = self.room_light_overrides.get((room, effect_name))
        if override_name:
            effect_data = self.get_effect(override_name) or effect_data

        if effect_data.get('no_lights'):
            # Entry MARKER (VMM's MoopMarch): the POST carries occupancy,
            # route tracking and telemetry, but the room's look is owned
            # elsewhere (the occupied gradient) — no takeover, no theme
            # pause. Audio still goes out if the effect has any.
            await self.remote_host_manager.play_effect_audio(
                self._audio_effect_name(room, effect_name), rooms=[room],
                audio_params=effect_data.get('audio', {}))
            logger.info(f"Effect '{effect_name}' in room '{room}' is a "
                        f"no-lights marker; lighting untouched")
            return True, f"{effect_name} marker applied to room {room}"

        fixture_ids = self._room_fixture_ids(room, effect_data.get('fixture_role'))
        if not fixture_ids:
            return False, f"No lights found for room: {room}"
        # An effect that owns only SOME of the room's fixtures (an answer chirp
        # on the accent par) leaves the theme running: the theme already skips
        # interrupted fixtures, so the ambient par keeps breathing underneath
        # while the accent one reacts — the ebb and flow is the point.
        whole_room = len(fixture_ids) >= len(self._room_fixture_ids(room))

        logger.info(f"Applying effect '{effect_name}' to room '{room}'"
                    + (f" as '{override_name}'" if override_name else '')
                    + ('' if whole_room else f" (accent fixtures only: {fixture_ids})"))
        # The lock makes the takeover atomic: cancel whatever is running, then
        # register the new task before anyone else can touch this room.
        async with self.room_locks[room]:
            await self._cancel_effect_in_room(room)
            if whole_room:
                self.theme_manager.pause_theme_for_room(room)
            effect_task = asyncio.create_task(self._run_effect(
                room, fixture_ids, effect_data, effect_name, manage_theme=whole_room))
            self.effect_tasks[room] = effect_task

        try:
            await effect_task
        except asyncio.CancelledError:
            if effect_task.cancelled():
                logger.info(f"Effect '{effect_name}' in room '{room}' was superseded")
                return True, f"{effect_name} superseded by a newer effect in room {room}"
            raise  # this request was cancelled; the effect task itself keeps running
        except Exception as e:
            logger.error(f"Error applying effect '{effect_name}' to room '{room}': {e}", exc_info=True)
            return False, str(e)
        return True, f"{effect_name} effect applied to room {room}"

    async def _run_effect(self, room, fixture_ids, effect_data, effect_name, send_audio=True,
                          manage_theme=True):
        """The per-room effect task. Owns its cleanup: only the task still registered
        for the room resumes the theme, so a takeover can never unbalance pause/resume.
        manage_theme=False for accent-fixture effects, which never paused it."""
        hooks = self.effect_hooks.get(effect_name) or {}
        completed = False
        try:
            if hooks.get('start'):
                try:
                    hooks['start'](room)
                except Exception as e:
                    logger.error(f"Start hook for '{effect_name}' failed: {e}", exc_info=True)
            if send_audio:
                await self.remote_host_manager.play_effect_audio(self._audio_effect_name(room, effect_name),
                                                                 rooms=[room],
                                                                 audio_params=effect_data.get('audio', {}))
            await self._run_lights(fixture_ids, effect_data)
            completed = True
        finally:
            # A run that didn't complete was cancelled (supersede/stop) or crashed;
            # let the hook owner abort whatever it scheduled (pending photo capture).
            if not completed and hooks.get('cancel'):
                try:
                    hooks['cancel'](room)
                except Exception as e:
                    logger.error(f"Cancel hook for '{effect_name}' failed: {e}", exc_info=True)
            if self.effect_tasks.get(room) is asyncio.current_task():
                del self.effect_tasks[room]
                # Effects are transient: clear their last frame so it can't stay
                # latched (several end on a bright hold — without this, a room
                # with no theme stays stuck white after the effect completes).
                for fixture_id in fixture_ids:
                    self.dmx_state_manager.reset_fixture(fixture_id)
                if manage_theme:
                    self.theme_manager.resume_theme_for_room(room)

    async def _cancel_effect_in_room(self, room):
        """Cancel and await the room's running effect, then stop its audio.
        Returns True if an effect was cancelled. Caller must hold the room's lock."""
        effect_task = self.effect_tasks.pop(room, None)
        if not effect_task:
            return False
        logger.info(f"Stopping active effect in room: {room}")
        effect_task.cancel()
        try:
            await effect_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Cancelled effect in room {room} ended with error: {e}")
        await self.remote_host_manager.send_audio_command(room, 'audio_stop')
        return True

    async def _run_lights(self, fixture_ids, effect_data):
        # One interpolator per fixture: each keeps its own monotonic step cursor.
        # Non-exempt effects play through the continuous palette clamp — the
        # step data can be clean while a cross-fade between hues still passes
        # through cream/yellow; guarding the PLAYED frame closes that for
        # every effect, including runtime-rebuilt ones (CuddlePuddle).
        def frame_fn(fn):
            if effect_data.get('palette_exempt'):
                return fn
            return lambda t: (list(fn(t)) if self._palette_exempt_at(effect_data, t)
                              else palette_clamp_frame(list(fn(t))))

        await asyncio.gather(*(
            self.interrupt_handler.interrupt_fixture(fixture_id, effect_data['duration'],
                                                     frame_fn(get_effect_step_values(effect_data)))
            for fixture_id in fixture_ids
        ))

    async def apply_effect_to_all_rooms(self, effect_name, audio_params=None):
        effect_data = self.get_effect(effect_name)
        if not effect_data:
            return False, f"{effect_name} effect not found"

        all_rooms = list(self.light_config_manager.get_room_layout().keys())
        logger.info(f"Applying effect '{effect_name}' to all rooms")

        # Hold every room's lock (fixed order, so no deadlock with single-room
        # triggers) while taking over: cancel running effects first so their
        # audio_stop commands can't kill the broadcast audio sent next.
        tasks = []
        async with AsyncExitStack() as stack:
            for room in all_rooms:
                await stack.enter_async_context(self.room_locks[room])
            for room in all_rooms:
                await self._cancel_effect_in_room(room)
            # One audio command per connected client covers every zone at once
            await self.remote_host_manager.play_effect_audio(
                effect_name, audio_params=audio_params or effect_data.get('audio', {}))
            for room in all_rooms:
                fixture_ids = self._room_fixture_ids(room)
                if not fixture_ids:
                    continue
                self.theme_manager.pause_theme_for_room(room)
                task = asyncio.create_task(
                    self._run_effect(room, fixture_ids, effect_data, effect_name, send_audio=False))
                self.effect_tasks[room] = task
                tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)
        errors = [r for r in results
                  if isinstance(r, Exception) and not isinstance(r, asyncio.CancelledError)]
        for error in errors:
            logger.error(f"Error during all-rooms effect execution: {error}")
        success = not errors
        return success, f"{effect_name} effect {'triggered' if success else 'failed to trigger'} in all rooms"

    async def stop_current_effect(self, room=None):
        """Stop the current effect in one room, or in all rooms if room is None."""
        if room is not None:
            await self.stop_effect_in_room(room)
            return
        for r in list(self.light_config_manager.get_room_layout().keys()):
            await self.stop_effect_in_room(r, send_audio=False)
        # One broadcast catches audio whose lighting already finished (long or
        # looping files leave no task to cancel): stop-all must mean silence.
        await self.remote_host_manager.send_audio_command(None, 'audio_stop')

    async def stop_effect_in_room(self, room, send_audio=True):
        async with self.room_locks[room]:
            stopped = await self._cancel_effect_in_room(room)
            if stopped:
                for fixture_id in self._room_fixture_ids(room):
                    self.dmx_state_manager.reset_fixture(fixture_id)
            elif send_audio:
                # Audio can outlive the lights; an explicit per-room stop must
                # silence the room even with no lighting task left to cancel.
                await self.remote_host_manager.send_audio_command(room, 'audio_stop')
            # Hand the room back to the theme even when there was nothing left to
            # cancel: a room vacated long after its entry effect finished must
            # still end up on ambient. resume is a set discard, so repeating it
            # costs nothing and can never unbalance a pause.
            self.theme_manager.resume_theme_for_room(room)
            return stopped

    # --- Theme / audio passthroughs used by the API ---

    def set_room_occupied(self, room, occupied):
        self.theme_manager.set_room_occupied(room, occupied)

    def set_master_brightness(self, brightness):
        self.theme_manager.set_master_brightness(brightness)

    async def set_current_theme_async(self, theme_name):
        return await self.theme_manager.set_current_theme_async(theme_name)

    async def stop_current_theme_async(self):
        await self.theme_manager.stop_current_theme_async()

    def stop_current_theme(self):
        self.theme_manager.stop_current_theme()

    async def set_next_theme_async(self):
        return await self.theme_manager.set_next_theme_async()

    def get_all_themes(self):
        return self.theme_manager.get_all_themes()

    async def update_theme_value(self, control_id, value):
        return await self.theme_manager.update_theme_value(control_id, value)
