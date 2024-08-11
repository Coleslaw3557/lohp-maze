import logging

logger = logging.getLogger(__name__)

def create_police_lights_effect():
    police_lights_effect = {
        "duration": 10.0,
        "description": "Alternating red and blue flashes simulating police lights",
        "audio_file": "policelights.mp3",
        "steps": []
    }
    for i in range(20):  # 20 cycles to fill 10 seconds
        t = i * 0.5
        police_lights_effect["steps"].extend([
            {"time": t, "channels": {"total_dimming": 255, "r_dimming": 255, "b_dimming": 0, "g_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}},
            {"time": t + 0.5, "channels": {"total_dimming": 255, "r_dimming": 0, "b_dimming": 255, "g_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}}
        ])
    police_lights_effect["steps"].append({"time": 15.0, "channels": {"total_dimming": 0, "r_dimming": 0, "b_dimming": 0, "g_dimming": 0, "w_dimming": 0, "total_strobe": 0, "function_selection": 0, "function_speed": 0}})
    logger.debug(f"Created Police Lights effect: {police_lights_effect}")
    logger.info(f"Police Lights effect created with {len(police_lights_effect['steps'])} steps over {police_lights_effect['duration']} seconds")
    return police_lights_effect
