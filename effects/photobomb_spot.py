import logging
import math

logger = logging.getLogger(__name__)

def create_photobomb_spot_effect():
    photobomb_spot_effect = {
        "duration": 5.0,
        "description": "Spotlight effect for the Photo Bomb room with a quick flash and fade",
        "steps": []
    }
    
    num_steps = 100  # 20 steps per second for smooth transition
    for i in range(num_steps + 1):
        t = i * (5.0 / num_steps)
        progress = i / num_steps
        
        # Quick flash and fade
        intensity = math.exp(-3 * progress)  # Exponential decay
        
        photobomb_spot_effect["steps"].append({
            "time": t,
            "channels": {
                "total_dimming": int(255 * intensity),
                "r_dimming": int(255 * intensity),
                "g_dimming": int(255 * intensity),
                "b_dimming": int(255 * intensity),
                "w_dimming": int(255 * intensity),
                "total_strobe": 0,
                "function_selection": 0,
                "function_speed": 0
            }
        })
    
    logger.debug(f"Created Photo Bomb Spotlight effect: {photobomb_spot_effect}")
    logger.info(f"Photo Bomb Spotlight effect created with {len(photobomb_spot_effect['steps'])} steps over {photobomb_spot_effect['duration']} seconds")
    return photobomb_spot_effect
