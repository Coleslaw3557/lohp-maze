import random
import math
import logging

logger = logging.getLogger(__name__)

def create_lightning_storm_effect():
    duration = 600.0  # 10 minutes
    lightning_storm_effect = {
        "duration": duration,
        "description": "A 10-minute rain and thunderstorm simulation with synchronized lightning flashes",
        "steps": []
    }

    # Simulate background rain
    rain_intensity = 20  # Constant dim blue light for rain
    lightning_storm_effect["steps"].append({
        "time": 0,
        "channels": {
            "total_dimming": rain_intensity,
            "r_dimming": 0,
            "g_dimming": 0,
            "b_dimming": rain_intensity,
            "w_dimming": 0,
            "total_strobe": 0,
            "function_selection": 0,
            "function_speed": 0
        }
    })

    # Add lightning flashes
    lightning_timings = [
        15, 45, 90, 120, 180, 240, 300, 360, 420, 480, 540  # Approximate timings based on the spectrogram
    ]

    for flash_time in lightning_timings:
        # Bright flash
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
        
        # Quick fade to rain
        lightning_storm_effect["steps"].append({
            "time": flash_time + 0.1,
            "channels": {
                "total_dimming": rain_intensity,
                "r_dimming": 0,
                "g_dimming": 0,
                "b_dimming": rain_intensity,
                "w_dimming": 0,
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })

    # End the effect
    lightning_storm_effect["steps"].append({
        "time": duration,
        "channels": {
            "total_dimming": 0,
            "r_dimming": 0,
            "g_dimming": 0,
            "b_dimming": 0,
            "w_dimming": 0,
            "total_strobe": 0,
            "function_selection": 0,
            "function_speed": 0
        }
    })

    logger.debug(f"Created LightningStorm effect: {lightning_storm_effect}")
    logger.info(f"LightningStorm effect created with {len(lightning_storm_effect['steps'])} steps over {duration} seconds")
    return lightning_storm_effect
