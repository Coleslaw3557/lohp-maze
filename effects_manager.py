import logging
import asyncio
from effects import (
    create_lightning_effect, create_police_lights_effect, create_gate_inspection_effect,
    create_gate_greeters_effect, create_wrong_answer_effect, create_correct_answer_effect,
    create_entrance_effect, create_guy_line_climb_effect, create_spark_pony_effect,
    create_porto_standby_effect, create_porto_hit_effect, create_cuddle_puddle_effect,
    create_photobomb_bg_effect, create_photobomb_spot_effect, create_deep_playa_bg_effect,
    create_deep_playa_hit_effect, create_image_enhancement_effect, create_bike_lock_room_effect,
    create_no_friends_monday_effect, create_lightning_storm_effect
)
from theme_manager import ThemeManager
from effect_utils import get_effect_step_values
from interrupt_handler import InterruptHandler

logger = logging.getLogger(__name__)


class EffectsManager:
    def __init__(self, light_config_manager, dmx_state_manager, remote_host_manager, audio_manager):
        self.light_config_manager = light_config_manager
        self.dmx_state_manager = dmx_state_manager
        self.remote_host_manager = remote_host_manager
        self.audio_manager = audio_manager
        self.interrupt_handler = InterruptHandler(dmx_state_manager)
        self.theme_manager = ThemeManager(dmx_state_manager, light_config_manager, self.interrupt_handler)
        self.effect_tasks = {}  # room -> asyncio.Task of the running effect
        self.effects = {
            "Lightning": create_lightning_effect(),
            "PoliceLights": create_police_lights_effect(),
            "GateInspection": create_gate_inspection_effect(),
            "GateGreeters": create_gate_greeters_effect(),
            "WrongAnswer": create_wrong_answer_effect(),
            "CorrectAnswer": create_correct_answer_effect(),
            "Entrance": create_entrance_effect(),
            "GuyLineClimb": create_guy_line_climb_effect(),
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
            "NoFriendsMonday": create_no_friends_monday_effect(),
            "LightningStorm": create_lightning_storm_effect(),
        }
        logger.info(f"Initialized {len(self.effects)} effects")

    def get_effect(self, effect_name):
        return self.effects.get(effect_name)

    def get_all_effects(self):
        return self.effects

    def get_effects_list(self):
        return {name: data.get('description', 'No description available')
                for name, data in self.effects.items()}

    def _room_fixture_ids(self, room):
        lights = self.light_config_manager.get_room_layout().get(room, [])
        return [(light['start_address'] - 1) // 8 for light in lights]

    async def apply_effect_to_room(self, room, effect_name, effect_data=None):
        # Cancel whatever is already running in this room
        await self.stop_effect_in_room(room)

        if effect_data is None:
            effect_data = self.get_effect(effect_name)
        if not effect_data:
            return False, f"{effect_name} effect not found"

        fixture_ids = self._room_fixture_ids(room)
        if not fixture_ids:
            return False, f"No lights found for room: {room}"

        logger.info(f"Applying effect '{effect_name}' to room '{room}'")
        self.theme_manager.pause_theme_for_room(room)
        effect_task = asyncio.create_task(self._run_effect(room, fixture_ids, effect_data, effect_name))
        self.effect_tasks[room] = effect_task
        try:
            await effect_task
        except asyncio.CancelledError:
            logger.info(f"Effect '{effect_name}' in room '{room}' was cancelled")
        except Exception as e:
            logger.error(f"Error applying effect '{effect_name}' to room '{room}': {e}", exc_info=True)
            return False, str(e)
        finally:
            self.effect_tasks.pop(room, None)
            self.theme_manager.resume_theme_for_room(room)
        return True, f"{effect_name} effect applied to room {room}"

    async def _run_effect(self, room, fixture_ids, effect_data, effect_name):
        await self.remote_host_manager.play_effect_audio(effect_name, rooms=[room],
                                                         audio_params=effect_data.get('audio', {}))
        await self._run_lights(fixture_ids, effect_data)

    async def _run_lights(self, fixture_ids, effect_data):
        # One interpolator per fixture: each keeps its own monotonic step cursor
        await asyncio.gather(*(
            self.interrupt_handler.interrupt_fixture(fixture_id, effect_data['duration'],
                                                     get_effect_step_values(effect_data))
            for fixture_id in fixture_ids
        ))

    async def apply_effect_to_all_rooms(self, effect_name, audio_params=None):
        effect_data = self.get_effect(effect_name)
        if not effect_data:
            return False, f"{effect_name} effect not found"

        all_rooms = list(self.light_config_manager.get_room_layout().keys())
        logger.info(f"Applying effect '{effect_name}' to all rooms")

        # Cancel anything already running so this takes over cleanly
        await self.stop_current_effect()

        # One audio command per connected client; a stoppable lighting task per room
        await self.remote_host_manager.play_effect_audio(effect_name, audio_params=audio_params)
        tasks = {}
        for room in all_rooms:
            self.theme_manager.pause_theme_for_room(room)
            task = asyncio.create_task(self._run_lights(self._room_fixture_ids(room), effect_data))
            tasks[room] = task
            self.effect_tasks[room] = task
        try:
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            for result in results:
                if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                    logger.error(f"Error during effect execution: {result}")
            success = not any(isinstance(result, Exception) for result in results)
        finally:
            for room, task in tasks.items():
                if self.effect_tasks.get(room) is task:
                    self.effect_tasks.pop(room, None)
                self.theme_manager.resume_theme_for_room(room)

        return success, f"{effect_name} effect {'triggered' if success else 'failed to trigger'} in all rooms"

    async def stop_current_effect(self, room=None):
        """Stop the current effect in one room, or in all rooms if room is None."""
        rooms = [room] if room else list(self.light_config_manager.get_room_layout().keys())
        for r in rooms:
            await self.stop_effect_in_room(r)

    async def stop_effect_in_room(self, room):
        effect_task = self.effect_tasks.pop(room, None)
        if effect_task:
            logger.info(f"Stopping active effect in room: {room}")
            effect_task.cancel()
            try:
                await effect_task
            except asyncio.CancelledError:
                pass
            for fixture_id in self._room_fixture_ids(room):
                self.dmx_state_manager.reset_fixture(fixture_id)
            await self.remote_host_manager.send_audio_command(room, 'audio_stop')
            if self.theme_manager.current_theme:
                await self.theme_manager.apply_theme_to_room(room)

    # --- Theme / music passthroughs used by the API ---

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

    async def start_music(self):
        return await self.remote_host_manager.start_background_music()

    async def stop_music(self):
        return await self.remote_host_manager.stop_background_music()
