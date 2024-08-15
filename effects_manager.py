import json
import logging
import asyncio
import os
import time
from effects import (
    create_lightning_effect, create_police_lights_effect, create_gate_inspection_effect,
    create_gate_greeters_effect, create_wrong_answer_effect, create_correct_answer_effect,
    create_entrance_effect, create_guy_line_climb_effect, create_spark_pony_effect,
    create_porto_standby_effect, create_porto_hit_effect, create_cuddle_puddle_effect,
    create_photobomb_bg_effect, create_photobomb_spot_effect, create_deep_playa_bg_effect,
    create_deep_playa_hit_effect, create_image_enhancement_effect, create_bike_lock_room_effect,
    create_no_friends_monday_effect
)
from theme_manager import ThemeManager
from effect_utils import get_effect_step_values
from interrupt_handler import InterruptHandler
from sync_manager import SyncManager

logger = logging.getLogger(__name__)

class EffectsManager:
    def __init__(self, config_file='effects_config.json', light_config_manager=None, dmx_state_manager=None, remote_host_manager=None, audio_manager=None):
        self.config_file = config_file
        self.effects = self.load_config()
        self.room_effects = {}
        self.light_config_manager = light_config_manager
        self.dmx_state_manager = dmx_state_manager
        self.remote_host_manager = remote_host_manager
        self.audio_manager = audio_manager
        self.interrupt_handler = InterruptHandler(dmx_state_manager, None)  # Temporarily set to None
        self.theme_manager = ThemeManager(dmx_state_manager, light_config_manager, self.interrupt_handler)
        self.interrupt_handler.theme_manager = self.theme_manager  # Set the theme_manager after initialization
        self.effect_buffer = {}
        self.sync_manager = SyncManager()
        self.active_effects = {}  # Dictionary to track active effects per room
        self.previous_values = {}  # Store previous values for smoothing
        self.smoothing_factor = 0.2  # Adjust this value to control smoothing (0.0 to 1.0)
        self.update_frequency = 10  # Set update frequency to 10 Hz
        self.effect_tasks = {}  # New dictionary to track effect tasks per room
        
        logger.info(f"InterruptHandler successfully initialized: {self.interrupt_handler}")
        
        # Initialize all effects
        self.initialize_effects()

    def update_frequency(self, new_frequency):
        self.update_frequency = new_frequency
        self.theme_manager.frequency = new_frequency
        logger.info(f"Update frequency set to {new_frequency} Hz")

    def load_config(self):
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            logger.info(f"Effects configuration loaded from {self.config_file}")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file {self.config_file} not found.")
            return {}
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {self.config_file}.")
            return {}

    def save_config(self):
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.effects, f, indent=4)
        except IOError:
            logger.error(f"Error writing to {self.config_file}")

    def get_effect(self, effect_name):
        return self.effects.get(effect_name)

    def add_effect(self, effect_name, effect_data):
        self.effects[effect_name] = effect_data
        self.save_config()

    def update_effect(self, effect_name, effect_data):
        if effect_name in self.effects:
            self.effects[effect_name] = effect_data
            self.save_config()
            logger.info(f"Effect updated: {effect_name}")
        else:
            logger.warning(f"No effect found: {effect_name}")

    def remove_effect(self, effect_name):
        if effect_name in self.effects:
            del self.effects[effect_name]
            self.save_config()
            logger.info(f"Effect removed: {effect_name}")
        else:
            logger.warning(f"No effect found: {effect_name}")

    async def stop_effect_in_room(self, room):
        if room in self.effect_tasks:
            logger.info(f"Stopping active effect in room: {room}")
            effect_task = self.effect_tasks[room]
            effect_task.cancel()
            try:
                await effect_task
            except asyncio.CancelledError:
                pass
            del self.effect_tasks[room]
            
            # Reset fixtures in the room
            room_layout = self.light_config_manager.get_room_layout()
            lights = room_layout.get(room, [])
            fixture_ids = [(light['start_address'] - 1) // 8 for light in lights]
            for fixture_id in fixture_ids:
                self.dmx_state_manager.reset_fixture(fixture_id)
            
            # Stop audio
            await self.remote_host_manager.send_audio_command(room, 'audio_stop')
        else:
            logger.info(f"No active effect to stop in room: {room}")

    async def apply_effect_to_room(self, room, effect_name, effect_data=None):
        logger.info(f"Starting to apply effect '{effect_name}' to room '{room}'")
        
        # Stop any ongoing effect in the room
        await self.stop_effect_in_room(room)
        
        if effect_data is None:
            effect_data = self.get_effect(effect_name)
        if not effect_data:
            logger.error(f"{effect_name} effect not found")
            return False, f"{effect_name} effect not found"

        room_layout = self.light_config_manager.get_room_layout()
        lights = room_layout.get(room, [])
        if not lights:
            logger.error(f"No lights found for room: {room}")
            return False, f"No lights found for room: {room}"

        fixture_ids = [(light['start_address'] - 1) // 8 for light in lights]
        
        logger.info(f"Applying effect '{effect_name}' to room '{room}'")
        
        self.room_effects[room] = effect_name
        
        # Pause the theme for this room
        self.theme_manager.pause_theme_for_room(room)
        
        # Instruct the client to play the audio only once at the beginning
        await self.remote_host_manager.send_audio_command(room, 'play_effect_audio', {'effect_name': effect_name})
        
        # Create a new task for this effect
        effect_task = asyncio.create_task(self._run_effect(room, fixture_ids, effect_data, effect_name))
        
        # Store the task in the effect_tasks dictionary
        if room in self.effect_tasks:
            # Cancel the previous effect task if it exists
            self.effect_tasks[room].cancel()
        self.effect_tasks[room] = effect_task
        
        try:
            # Wait for the effect task to complete
            await effect_task
        except asyncio.CancelledError:
            logger.info(f"Effect '{effect_name}' in room '{room}' was cancelled")
        except Exception as e:
            error_message = f"Error applying effect '{effect_name}' to room '{room}': {str(e)}"
            logger.error(error_message, exc_info=True)
            return False, error_message
        finally:
            # Ensure the room effect is cleared even if an exception occurs
            if room in self.room_effects:
                del self.room_effects[room]
            # Remove the task from effect_tasks
            self.effect_tasks.pop(room, None)
            # Resume the theme for this room
            self.theme_manager.resume_theme_for_room(room)
        
        logger.info(f"Effect '{effect_name}' application completed in room '{room}'")
        return True, f"{effect_name} effect applied to room {room}"

    async def _run_effect(self, room, fixture_ids, effect_data, effect_name):
        tasks = []
        # Use the interrupt system to apply the effect
        for fixture_id in fixture_ids:
            task = self.interrupt_handler.interrupt_fixture(fixture_id, effect_data['duration'], get_effect_step_values(effect_data))
            tasks.append(task)
        
        # Run all lighting tasks concurrently
        await asyncio.gather(*tasks)

    # Remove the _apply_audio_effect method as it's no longer needed

    async def _run_effect(self, room, fixture_ids, effect_data, effect_name):
        try:
            # Prepare and play audio
            audio_params = effect_data.get('audio', {})
            audio_success = await self.remote_host_manager.play_audio_in_room(room, effect_name, audio_params)
            
            # Apply lighting effect
            lighting_task = self._apply_lighting_effect(room, effect_data)
            
            # Run lighting task
            await lighting_task
            
            logger.info(f"Effect '{effect_name}' application completed in room '{room}'. Audio success: {audio_success}")
        except asyncio.CancelledError:
            logger.info(f"Effect '{effect_name}' cancelled in room '{room}'")
        finally:
            self.room_effects.pop(room, None)
            if room in self.active_effects:
                del self.active_effects[room]

    async def _apply_lighting_effect(self, room, effect_data):
        room_layout = self.light_config_manager.get_room_layout()
        lights = room_layout.get(room, [])
        if not lights:
            logger.warning(f"No lights found for room: {room}")
            return True  # Return True to not fail the overall effect

        fixture_ids = [(light['start_address'] - 1) // 8 for light in lights]
        
        lighting_tasks = [self._apply_effect_to_fixture(fixture_id, effect_data) for fixture_id in fixture_ids]
        lighting_results = await asyncio.gather(*lighting_tasks, return_exceptions=True)
        
        lighting_success = all(isinstance(result, bool) and result for result in lighting_results)
        
        if lighting_success:
            logger.info(f"Lighting effect application completed successfully in room '{room}'")
        else:
            logger.error(f"Failed to apply lighting effect in room '{room}'")
            for i, result in enumerate(lighting_results):
                if isinstance(result, Exception):
                    logger.error(f"Error applying effect to fixture {fixture_ids[i]}: {str(result)}")
                elif not result:
                    logger.error(f"Failed to apply effect to fixture {fixture_ids[i]}")
        
        return lighting_success

    def get_audio_file(self, effect_name):
        audio_file = f"audio_files/{effect_name.lower()}.mp3"
        if os.path.exists(audio_file):
            logger.info(f"Audio file found for effect '{effect_name}': {audio_file}")
            return audio_file
        logger.warning(f"Audio file not found for effect '{effect_name}': {audio_file}")
        return None

    async def _apply_effect_to_fixture(self, fixture_id, effect_data):
        try:
            step_values = get_effect_step_values(effect_data)
            smoothed_values = self._smooth_values(fixture_id, step_values)
            await self.interrupt_handler.interrupt_fixture(
                fixture_id,
                effect_data['duration'],
                smoothed_values
            )
            logger.debug(f"Effect applied to fixture {fixture_id}")
        except Exception as e:
            logger.error(f"Error applying effect to fixture {fixture_id}: {str(e)}")

    def _smooth_values(self, fixture_id, step_values):
        def smoothed_step_values(elapsed_time):
            new_values = step_values(elapsed_time)
            if fixture_id not in self.previous_values:
                self.previous_values[fixture_id] = new_values
                return new_values

            smoothed = []
            for i, value in enumerate(new_values):
                prev_value = self.previous_values[fixture_id][i]
                smoothed_value = prev_value + (value - prev_value) * self.smoothing_factor
                smoothed.append(int(smoothed_value))

            self.previous_values[fixture_id] = smoothed
            return smoothed

        return smoothed_step_values

    def get_all_effects(self):
        return self.effects

    def get_effects_list(self):
        return {name: data.get('description', 'No description available') 
                for name, data in self.effects.items()}

    def set_master_brightness(self, brightness):
        self.theme_manager.set_master_brightness(brightness)

    async def set_current_theme_async(self, theme_name):
        logger.info(f"Setting current theme to: {theme_name}")
        result = await self.theme_manager.set_current_theme_async(theme_name)
        logger.info(f"Theme set result: {result}")
        return result

    async def set_current_theme(self, theme_name):
        logger.info(f"Setting current theme to: {theme_name}")
        return await self.set_current_theme_async(theme_name)

    async def stop_current_theme_async(self):
        logger.info("Stopping current theme asynchronously")
        await self.theme_manager.stop_current_theme_async()

    def stop_current_theme(self):
        logger.info("Stopping current theme")
        self.theme_manager.stop_current_theme()

    async def set_next_theme_async(self):
        logger.info("Setting next theme")
        return await self.theme_manager.set_next_theme_async()

    def get_all_themes(self):
        logger.info("Getting all themes")
        return self.theme_manager.get_all_themes()

    def get_theme(self, theme_name):
        logger.info(f"Getting theme: {theme_name}")
        return self.theme_manager.get_theme(theme_name)

    async def start_music(self):
        logger.info("Starting background music")
        return await self.remote_host_manager.start_background_music()

    async def stop_music(self):
        logger.info("Stopping background music")
        return await self.remote_host_manager.stop_background_music()

    async def update_theme_value(self, control_id, value):
        logger.info(f"Updating theme value: {control_id} to {value}")
        return await self.theme_manager.update_theme_value(control_id, value)

    async def prepare_audio_for_all_rooms(self, effect_name):
        logger.info(f"Preparing audio for effect {effect_name} in all rooms")
        effect_data = self.get_effect(effect_name)
        if not effect_data:
            logger.error(f"{effect_name} effect not found")
            return False

        room_layout = self.light_config_manager.get_room_layout()
        for room in room_layout.keys():
            audio_file = self.get_audio_file(effect_name)
            if audio_file:
                await self.remote_host_manager.prepare_audio_stream(room, audio_file, effect_data.get('audio', {}), effect_name)
            else:
                logger.warning(f"No audio file found for effect {effect_name} in room {room}")
        
        return True

    def initialize_effects(self):
        effects = [
            ("Lightning", create_lightning_effect()),
            ("PoliceLights", create_police_lights_effect()),
            ("GateInspection", create_gate_inspection_effect()),
            ("GateGreeters", create_gate_greeters_effect()),
            ("WrongAnswer", create_wrong_answer_effect()),
            ("CorrectAnswer", create_correct_answer_effect()),
            ("Entrance", create_entrance_effect()),
            ("GuyLineClimb", create_guy_line_climb_effect()),
            ("SparkPony", create_spark_pony_effect()),
            ("PortoStandBy", create_porto_standby_effect()),
            ("PortoHit", create_porto_hit_effect()),
            ("CuddlePuddle", create_cuddle_puddle_effect()),
            ("PhotoBomb-BG", create_photobomb_bg_effect()),
            ("PhotoBomb-Spot", create_photobomb_spot_effect()),
            ("DeepPlaya-BG", create_deep_playa_bg_effect()),
            ("DeepPlaya-Hit", create_deep_playa_hit_effect()),
            ("ImageEnhancement", create_image_enhancement_effect()),
            ("BikeLockRoom", create_bike_lock_room_effect()),
            ("NoFriendsMonday", create_no_friends_monday_effect()),
        ]
        for effect_name, effect_data in effects:
            self.add_effect(effect_name, effect_data)
        logger.info(f"Initialized {len(effects)} effects")

    async def apply_effect_to_all_rooms(self, effect_name, effect_data):
        logger.info(f"Applying effect {effect_name} to all rooms")
        if not effect_data:
            logger.error(f"{effect_name} effect not found")
            return False, f"{effect_name} effect not found"

        room_layout = self.light_config_manager.get_room_layout()
        all_rooms = list(room_layout.keys())

        # Instruct all clients to play the audio
        await self.remote_host_manager.send_audio_command(all_rooms, 'play_effect_audio', {'effect_name': effect_name})

        # Pause themes for all rooms
        for room in all_rooms:
            self.theme_manager.pause_theme_for_room(room)

        # Apply lighting effect to all rooms simultaneously
        lighting_tasks = []
        for room in all_rooms:
            lights = room_layout.get(room, [])
            fixture_ids = [(light['start_address'] - 1) // 8 for light in lights]
            for fixture_id in fixture_ids:
                task = self.interrupt_handler.interrupt_fixture(fixture_id, effect_data['duration'], get_effect_step_values(effect_data))
                lighting_tasks.append(task)

        try:
            lighting_results = await asyncio.gather(*lighting_tasks, return_exceptions=True)
            success = all(isinstance(result, bool) and result for result in lighting_results)
            
            if success:
                logger.info(f"{effect_name} effect triggered in all rooms")
            else:
                logger.error(f"Failed to trigger {effect_name} effect in some rooms")
                for result in lighting_results:
                    if isinstance(result, Exception):
                        logger.error(f"Error during effect execution: {str(result)}")
        finally:
            # Resume themes for all rooms
            for room in all_rooms:
                self.theme_manager.resume_theme_for_room(room)

        return success, f"{effect_name} effect {'triggered' if success else 'failed to trigger'} in all rooms"

    async def prepare_effect_for_room(self, room, effect_name, effect_data):
        # Prepare the effect for a specific room (e.g., load audio, prepare lighting sequences)
        logger.info(f"Preparing effect {effect_name} for room {room}")
        # Add your preparation logic here
        pass

    async def execute_effect_in_room(self, room, effect_name, effect_data, audio_file):
        logger.info(f"Executing effect {effect_name} in room {room}")
        success, _ = await self.apply_effect_to_room(room, effect_name, effect_data, audio_file)
        return success

    async def stop_current_effect(self, room=None):
        """
        Stop the current effect in a specific room or all rooms.
        
        :param room: The room to stop the effect in. If None, stop in all rooms.
        """
        if room:
            rooms = [room]
        else:
            rooms = self.light_config_manager.get_room_layout().keys()
        
        for r in rooms:
            await self.stop_effect_in_room(r)
        
        logger.info("All specified effects stopped")

    async def stop_effect_in_room(self, room):
        if room in self.active_effects:
            logger.info(f"Stopping effect in room: {room}")
            # Stop lighting effect
            room_layout = self.light_config_manager.get_room_layout()
            lights = room_layout.get(room, [])
            fixture_ids = [(light['start_address'] - 1) // 8 for light in lights]
            
            for fixture_id in fixture_ids:
                self.dmx_state_manager.reset_fixture(fixture_id)
            
            # Stop audio
            await self.remote_host_manager.send_audio_command(room, 'audio_stop', None)
            
            # Remove from active effects
            del self.active_effects[room]
        else:
            logger.info(f"No active effect in room: {room}")
        
        # Restore theme if it's running
        if self.theme_manager.current_theme:
            await self.theme_manager.apply_theme_to_room(room)

    async def buffer_effect(self, room, effect_name, effect_data):
        logger.info(f"Buffering effect for room: {room}")
        effect_id = self.sync_manager.generate_effect_id()
        self.effect_buffer[effect_id] = {
            'rooms': [room] if isinstance(room, str) else room,
            'effect_name': effect_name,
            'effect_data': effect_data,
            'ready': False,
            'buffered_at': time.time()
        }
        # Clean up old buffered effects
        await self._clean_effect_buffer()
        return effect_id

    async def _clean_effect_buffer(self):
        current_time = time.time()
        expired_effects = [eid for eid, effect in self.effect_buffer.items() 
                           if current_time - effect['buffered_at'] > 300]  # 5 minutes expiration
        for eid in expired_effects:
            del self.effect_buffer[eid]
            logger.info(f"Removed expired effect {eid} from buffer")

    async def prepare_effect(self, effect_id):
        effect = self.effect_buffer[effect_id]
        rooms, effect_name, effect_data = effect['rooms'], effect['effect_name'], effect['effect_data']
        
        # Prepare lighting effect
        room_layout = self.light_config_manager.get_room_layout()
        for room in rooms:
            lights = room_layout.get(room, [])
            fixture_ids = [(light['start_address'] - 1) // 8 for light in lights]
        
            # Prepare audio effect
            audio_file = self.get_audio_file(effect_name)
            if audio_file:
                audio_params = effect_data.get('audio', {})
                await self.remote_host_manager.prepare_audio_stream(room, audio_file, audio_params, effect_name)
        
        effect['ready'] = True
        logger.info(f"Effect {effect_id} prepared for rooms {rooms}")

    async def prepare_effect_all_rooms(self, rooms, effect_name, effect_data):
        effect_id = self.sync_manager.generate_effect_id()
        self.effect_buffer[effect_id] = {
            'rooms': rooms,
            'effect_name': effect_name,
            'effect_data': effect_data,
            'ready': False,
            'buffered_at': time.time()
        }

        # Prepare audio for all rooms
        audio_file = self.get_audio_file(effect_name)
        audio_params = effect_data.get('audio', {})
        await self.remote_host_manager.prepare_audio_stream(rooms, audio_file, audio_params, effect_name)

        # Mark effect as ready
        self.effect_buffer[effect_id]['ready'] = True
        
        return effect_id

    async def execute_effect_all_rooms(self, effect_id):
        effect = self.effect_buffer[effect_id]
        rooms, effect_name, effect_data = effect['rooms'], effect['effect_name'], effect['effect_data']
        
        if not effect['ready']:
            logger.error(f"Effect {effect_id} not ready for execution")
            return False

        # Execute audio effect for all rooms simultaneously
        audio_params = effect_data.get('audio', {})
        audio_success = await self.remote_host_manager.play_audio_in_room(rooms, effect_name, audio_params)
        
        # Execute lighting effect for all rooms simultaneously
        lighting_tasks = [self._apply_lighting_effect(room, effect_data) for room in rooms]
        lighting_results = await asyncio.gather(*lighting_tasks)
        lighting_success = all(lighting_results)
        
        del self.effect_buffer[effect_id]
        
        return lighting_success and audio_success

    async def execute_effect(self, effect_id):
        effect = self.effect_buffer.get(effect_id)
        if not effect:
            logger.error(f"Effect {effect_id} not found in buffer")
            return False

        if not effect['ready']:
            logger.error(f"Effect {effect_id} not ready for execution")
            return False

        rooms = effect['rooms']
        effect_name = effect['effect_name']
        effect_data = effect['effect_data']

        try:
            # Stop any existing effects in the rooms
            for room in rooms:
                await self.stop_effect_in_room(room)

            # Execute audio effect for all rooms
            audio_tasks = [self.remote_host_manager.send_audio_command(room, 'play_effect_audio', {'effect_name': effect_name}) for room in rooms]

            # Execute lighting effect for all rooms simultaneously using the interrupt system
            lighting_tasks = []
            for room in rooms:
                room_layout = self.light_config_manager.get_room_layout()
                lights = room_layout.get(room, [])
                fixture_ids = [(light['start_address'] - 1) // 8 for light in lights]
                for fixture_id in fixture_ids:
                    lighting_tasks.append(self.interrupt_handler.interrupt_fixture(
                        fixture_id,
                        effect_data['duration'],
                        get_effect_step_values(effect_data)
                    ))

            # Run all tasks concurrently
            results = await asyncio.gather(*audio_tasks, *lighting_tasks, return_exceptions=True)
            
            success = all(not isinstance(result, Exception) for result in results)

            if not success:
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"Error during effect execution: {str(result)}")

            del self.effect_buffer[effect_id]

            # Update active effects
            for room in rooms:
                self.active_effects[room] = effect_id

            return success
        except Exception as e:
            logger.error(f"Unexpected error during effect execution: {str(e)}", exc_info=True)
            return False

    async def _apply_lighting_effect(self, room, effect_data):
        room_layout = self.light_config_manager.get_room_layout()
        lights = room_layout.get(room, [])
        if not lights:
            logger.warning(f"No lights found for room: {room}")
            return True  # Return True to not fail the overall effect

        fixture_ids = [(light['start_address'] - 1) // 8 for light in lights]
        
        lighting_tasks = [self._apply_effect_to_fixture(fixture_id, effect_data) for fixture_id in fixture_ids]
        lighting_results = await asyncio.gather(*lighting_tasks, return_exceptions=True)
        
        lighting_success = all(isinstance(result, bool) and result for result in lighting_results)
        
        if lighting_success:
            logger.info(f"Lighting effect application completed successfully in room '{room}'")
        else:
            logger.error(f"Failed to apply lighting effect in room '{room}'")
            for i, result in enumerate(lighting_results):
                if isinstance(result, Exception):
                    logger.error(f"Error applying effect to fixture {fixture_ids[i]}: {str(result)}")
                elif not result:
                    logger.error(f"Failed to apply effect to fixture {fixture_ids[i]}")
        
        return lighting_success

    async def _apply_audio_effect(self, room, effect_name):
        logger.info(f"Applying audio effect '{effect_name}' to room '{room}'")
        audio_config = self.audio_manager.get_audio_config(effect_name)
        if audio_config:
            logger.debug(f"Audio configuration found for effect '{effect_name}': {audio_config}")
            audio_file = self.audio_manager.get_audio_file(effect_name)
            if audio_file:
                logger.info(f"Audio file found for effect '{effect_name}': {audio_file}")
                try:
                    with open(audio_file, 'rb') as f:
                        audio_data = f.read()
                    logger.info(f"Audio stream prepared for effect '{effect_name}'. Sending to room '{room}'")
                    await self.remote_host_manager.send_audio_command(room, 'audio_start', audio_data)
                    return True
                except IOError as e:
                    logger.error(f"Error reading audio file for effect '{effect_name}': {str(e)}")
            else:
                logger.error(f"Audio file not found for effect '{effect_name}'")
        else:
            logger.warning(f"No audio configuration found for effect '{effect_name}'")
        return False

    async def _apply_effect_to_fixture(self, fixture_id, effect_data):
        try:
            logger.debug(f"Applying effect to fixture {fixture_id}")
            step_values = get_effect_step_values(effect_data)
            if not step_values:
                logger.error(f"No step values generated for fixture {fixture_id}")
                return False
            
            result = await self.interrupt_handler.interrupt_fixture(
                fixture_id,
                effect_data['duration'],
                step_values
            )
            if result:
                logger.debug(f"Effect applied successfully to fixture {fixture_id}")
                return True
            else:
                logger.error(f"Failed to apply effect to fixture {fixture_id}")
                return False
        except Exception as e:
            logger.error(f"Error applying effect to fixture {fixture_id}: {str(e)}", exc_info=True)
            return False
    async def _fade_to_black(self, room, fixture_ids, duration):
        start_time = time.time()
        while time.time() - start_time < duration:
            progress = (time.time() - start_time) / duration
            tasks = []
            for fixture_id in fixture_ids:
                current_values = self.dmx_state_manager.get_fixture_state(fixture_id)
                faded_values = [int(value * (1 - progress)) for value in current_values]
                tasks.append(self._update_fixture(fixture_id, faded_values))
            await asyncio.gather(*tasks)
            await asyncio.sleep(1 / self.frequency)

    async def _fade_to_theme(self, room, fixture_ids, duration):
        start_time = time.time()
        while time.time() - start_time < duration:
            progress = (time.time() - start_time) / duration
            tasks = []
            for fixture_id in fixture_ids:
                current_values = self.dmx_state_manager.get_fixture_state(fixture_id)
                theme_values = self._generate_theme_values(room)
                interpolated_values = [int(current + (theme - current) * progress)
                                       for current, theme in zip(current_values, theme_values)]
                tasks.append(self._update_fixture(fixture_id, interpolated_values))
            await asyncio.gather(*tasks)
            await asyncio.sleep(1 / self.frequency)

    async def _apply_effect_to_fixture(self, fixture_id, effect_data):
        try:
            await self.interrupt_handler.interrupt_fixture(
                fixture_id,
                effect_data['duration'],
                get_effect_step_values(effect_data)
            )
            logger.debug(f"Effect applied to fixture {fixture_id}")
            return True
        except Exception as e:
            error_msg = f"Error applying effect to fixture {fixture_id}: {str(e)}"
            logger.error(error_msg)
            return False

    async def _update_fixture(self, fixture_id, values):
        self.dmx_state_manager.update_fixture(fixture_id, values)
        await asyncio.sleep(0)  # Yield control to allow other coroutines to run
    def _fade_to_black(self, room, fixture_ids, duration):
        start_time = time.time()
        while time.time() - start_time < duration:
            progress = (time.time() - start_time) / duration
            for fixture_id in fixture_ids:
                current_values = self.dmx_state_manager.get_fixture_state(fixture_id)
                faded_values = [int(value * (1 - progress)) for value in current_values]
                self.dmx_state_manager.update_fixture(fixture_id, faded_values)
            time.sleep(1 / 44)  # 44Hz update rate

    async def _fade_to_theme(self, room, fixture_ids, duration):
        start_time = time.time()
        while time.time() - start_time < duration:
            progress = (time.time() - start_time) / duration
            tasks = []
            for fixture_id in fixture_ids:
                current_values = self.dmx_state_manager.get_fixture_state(fixture_id)
                theme_values = self._generate_theme_values(room)
                interpolated_values = [int(current + (theme - current) * progress)
                                       for current, theme in zip(current_values, theme_values)]
                tasks.append(self._update_fixture(fixture_id, interpolated_values))
            await asyncio.gather(*tasks)
            await asyncio.sleep(1 / self.frequency)

    def _generate_theme_values(self, room):
        # This method should generate the current theme values for the room
        # You'll need to implement this based on your theme logic
        # For now, we'll return a placeholder
        return [128, 64, 32, 0, 255, 0, 0, 0]
    def _apply_room_channels(self, room, lights, room_channels):
        for light in lights:
            start_address = light['start_address']
            light_model = self.light_config_manager.get_light_config(light['model'])
            fixture_id = (start_address - 1) // 8
            if not self.interrupt_handler.is_fixture_interrupted(fixture_id):
                fixture_values = [0] * 8
                logger.debug(f"Applying theme to room {room}, light model {light['model']}")
                for channel, value in room_channels.items():
                    if channel in light_model['channels']:
                        channel_offset = light_model['channels'][channel]
                        fixture_values[channel_offset] = value
                        logger.debug(f"  Setting channel {channel} (offset {channel_offset}) to value {value}")
                    else:
                        logger.debug(f"  Channel {channel} not found in light model, skipping")
                self.dmx_state_manager.update_fixture(fixture_id, fixture_values)
                logger.debug(f"  Final fixture values: {fixture_values}")
            else:
                logger.debug(f"Skipping theme application for interrupted fixture {fixture_id} in room {room}")
