import random
import math
import logging

logger = logging.getLogger(__name__)

def create_lightning_storm_effect():
    duration = 600.0  # 10 minutes
    lightning_storm_effect = {
        "duration": duration,
        "description": "A 10-minute rain and thunderstorm simulation with synchronized lightning flashes and background blue light",
        "steps": []
    }

    # Lightning timings based on the spectrogram
    lightning_timings = [
        15, 45, 90, 120, 180, 240, 300, 360, 420, 480, 540
    ]

    # Background rain and blue light parameters
    rain_intensity = 20
    blue_intensity_min = 10
    blue_intensity_max = 30
    blue_fade_duration = 5.0  # Duration of one fade cycle

    # Generate steps for the entire duration
    current_time = 0
    while current_time <= duration:
        # Calculate blue light intensity
        blue_intensity = blue_intensity_min + (blue_intensity_max - blue_intensity_min) * (
            math.sin(2 * math.pi * current_time / blue_fade_duration) * 0.5 + 0.5
        )

        # Add step for background rain and blue light
        lightning_storm_effect["steps"].append({
            "time": current_time,
            "channels": {
                "total_dimming": max(rain_intensity, int(blue_intensity)),
                "r_dimming": 0,
                "g_dimming": 0,
                "b_dimming": int(blue_intensity),
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })

        # Check if it's time for a lightning flash
        if lightning_timings and current_time >= lightning_timings[0]:
            flash_time = lightning_timings.pop(0)
            
            # Bright initial flash
            lightning_storm_effect["steps"].append({
                "time": flash_time,
                "channels": {
                    "total_dimming": 255,
                    "r_dimming": 255,
                    "g_dimming": 255,
                    "b_dimming": 255,
                    "w_dimming": 255,
                    "total_strobe": 0,
                    "function_selection": 0,
                    "function_speed": 0
                }
            })
            
            # Quick dim
            lightning_storm_effect["steps"].append({
                "time": flash_time + 0.05,
                "channels": {
                    "total_dimming": 100,
                    "r_dimming": 100,
                    "g_dimming": 100,
                    "b_dimming": 100,
                    "w_dimming": 100,
                    "total_strobe": 0,
                    "function_selection": 0,
                    "function_speed": 0
                }
            })
            
            # Second flash
            lightning_storm_effect["steps"].append({
                "time": flash_time + 0.1,
                "channels": {
                    "total_dimming": 200,
                    "r_dimming": 200,
                    "g_dimming": 200,
                    "b_dimming": 200,
                    "w_dimming": 200,
                    "total_strobe": 0,
                    "function_selection": 0,
                    "function_speed": 0
                }
            })
            
            # Fade back to rain and blue light
            lightning_storm_effect["steps"].append({
                "time": flash_time + 0.2,
                "channels": {
                    "total_dimming": max(rain_intensity, int(blue_intensity)),
                    "r_dimming": 0,
                    "g_dimming": 0,
                    "b_dimming": int(blue_intensity),
                    "w_dimming": 0,
                    "total_strobe": 0,
                    "function_selection": 0,
                    "function_speed": 0
                }
            })

        current_time += 0.1  # 100ms steps for smooth transitions

    # Ensure the last step is at the exact duration
    lightning_storm_effect["steps"][-1]["time"] = duration

    logger.debug(f"Created LightningStorm effect: {lightning_storm_effect}")
    logger.info(f"LightningStorm effect created with {len(lightning_storm_effect['steps'])} steps over {duration} seconds")
    return lightning_storm_effect
